// Main application - a port of pose_trial/app.py.
// States: LINEUP -> DETECTED -> TRIAL (per round) -> ROUND_COMPLETE -> COMPLETE

import { PoseLandmarker, FilesetResolver } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/vision_bundle.mjs";
import { CONFIG } from "./config.js";
import { POSE_SCORERS, NOSE, formatCode } from "./poses.js";
import * as ui from "./ui.js";

const State = {
  LINEUP: "LINEUP",
  DETECTED: "DETECTED",
  TRIAL: "TRIAL",
  ROUND_COMPLETE: "ROUND_COMPLETE",
  COMPLETE: "COMPLETE",
};

// --- DOM ---
const setupEl = document.getElementById("setup");
const stageEl = document.getElementById("stage");
const statusEl = document.getElementById("setupStatus");
const startBtn = document.getElementById("startBtn");
const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");
const cameraSelect = document.getElementById("cameraSelect");
const camWarning = document.getElementById("camWarning");

// --- Game state ---
let landmarker = null;
let running = false;
let n = 2;
let dev = false;
let initialRoundIdx = 0;

let state, code, roundIdx;
let devIndex = 0; // dev mode walks the alphabet from A; reset at the start of a run
let lineupFullSince, detectedAt, completedAt, roundCompleteAt;
let solved, hold, personClocks;
let showInfo = false;
let showHint = false;
let lastVideoTime = -1;
let lastPeople = [];

const cfg = CONFIG;
const rounds = cfg.roundAlphabets;
const devLetters = [...new Set(rounds.join(""))].join("");

function generateCode(alphabet, count) {
  let s = "";
  for (let i = 0; i < count; i++) s += alphabet[Math.floor(Math.random() * alphabet.length)];
  return s;
}

function nextCode() {
  if (dev) {
    const letter = devLetters[devIndex % devLetters.length];
    devIndex += 1;
    return letter.repeat(n);
  }
  return generateCode(rounds[roundIdx], n);
}

// Counts how long a pose has been held. Time accumulates ONLY on frames where
// the pose is actually good. A break shorter than the grace period pauses the
// clock (so detector jitter does not punish anyone); a longer break clears it.
// With grace at 0 any red frame resets the hold immediately.
class HoldClock {
  constructor(graceSeconds) {
    this.grace = graceSeconds;
    this.reset();
  }
  reset() {
    this.held = 0.0;
    this.greenAt = null; // previous green frame, null if the last frame was red
    this.brokeAt = null; // when the current red streak started
  }
  update(green, now) {
    if (green) {
      if (this.greenAt !== null) this.held += now - this.greenAt;
      this.greenAt = now;
      this.brokeAt = null;
    } else {
      this.greenAt = null;
      if (this.brokeAt === null) this.brokeAt = now;
      if (now - this.brokeAt >= this.grace) this.held = 0.0;
    }
    return this.held;
  }
}

function resetTrialState() {
  solved = Array(n).fill(false);
  hold = new HoldClock(cfg.breakGraceSeconds);
  personClocks = Array.from({ length: n }, () => new HoldClock(cfg.breakGraceSeconds));
}

function restart() {
  roundIdx = initialRoundIdx;
  code = nextCode();
  console.log(`Pose code: ${formatCode(code)}`);
  state = dev ? State.TRIAL : State.LINEUP;
  lineupFullSince = null;
  resetTrialState();
}

// --- Camera selection ---
// Browsers only reveal camera labels once the user has granted access, so this
// runs again after the first successful getUserMedia to fill in real names.
async function populateCameras() {
  if (!navigator.mediaDevices?.enumerateDevices) return;
  let cams;
  try {
    cams = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
  } catch {
    return;
  }
  const previous = cameraSelect.value;
  cameraSelect.replaceChildren();
  const auto = document.createElement("option");
  auto.value = "";
  auto.textContent = "Default camera";
  cameraSelect.appendChild(auto);
  cams.forEach((d, i) => {
    const opt = document.createElement("option");
    opt.value = d.deviceId;
    opt.textContent = d.label || `Camera ${i + 1}`;
    cameraSelect.appendChild(opt);
  });
  if (previous && cams.some((d) => d.deviceId === previous)) cameraSelect.value = previous;
}

populateCameras();
navigator.mediaDevices?.addEventListener?.("devicechange", populateCameras);

// --- Black-frame watchdog ---
// Reading a downscaled copy keeps this cheap enough to run a couple times a second.
const probe = document.createElement("canvas");
probe.width = 32;
probe.height = 18;
const probeCtx = probe.getContext("2d", { willReadFrequently: true });
let darkSince = null;
let lastProbeAt = 0;
let cameraLabel = "";

function showCamWarning() {
  const other = cameraSelect.options.length > 2;
  const name = cameraLabel || cameraSelect.selectedOptions[0]?.textContent || "the selected camera";
  camWarning.innerHTML =
    `<strong>The camera is on, but every frame is black.</strong><br/>` +
    `Using: ${name}.<br/>` +
    `Check that nothing is covering the lens, that no other app or browser tab ` +
    `is holding the camera (close them and press Exit, then start again)` +
    (other ? `, or go back and pick a different camera.` : `.`);
  camWarning.classList.remove("hidden");
}

function checkCameraHealth(now) {
  if (now - lastProbeAt < 0.5) return;
  lastProbeAt = now;
  if (video.videoWidth === 0) return;
  probeCtx.drawImage(video, 0, 0, probe.width, probe.height);
  const d = probeCtx.getImageData(0, 0, probe.width, probe.height).data;
  let sum = 0;
  for (let i = 0; i < d.length; i += 4) sum += (d[i] + d[i + 1] + d[i + 2]) / 3;
  const mean = sum / (d.length / 4);
  if (mean < cfg.blackFrameThreshold) {
    darkSince = darkSince ?? now;
    if (now - darkSince >= cfg.blackFrameSeconds) showCamWarning();
  } else {
    darkSince = null;
    camWarning.classList.add("hidden");
  }
}

// --- Setup flow ---
startBtn.addEventListener("click", async () => {
  n = parseInt(document.getElementById("participants").value, 10);
  dev = document.getElementById("devMode").checked;
  initialRoundIdx = Math.max(0, Math.min(rounds.length - 1,
    parseInt(document.getElementById("startRound").value, 10) - 1));

  startBtn.disabled = true;
  try {
    statusEl.textContent = "Loading the pose model...";
    const vision = await FilesetResolver.forVisionTasks(cfg.wasmBaseUrl);
    landmarker = await PoseLandmarker.createFromOptions(vision, {
      baseOptions: { modelAssetPath: cfg.modelUrl, delegate: "GPU" },
      runningMode: "VIDEO",
      numPoses: n,
      minPoseDetectionConfidence: cfg.minPoseDetectionConfidence,
      minPosePresenceConfidence: cfg.minPosePresenceConfidence,
      minTrackingConfidence: cfg.minTrackingConfidence,
    });

    statusEl.textContent = "Requesting camera...";
    const chosen = cameraSelect.value;
    const constraints = {
      width: cfg.frameWidth,
      height: cfg.frameHeight,
      ...(chosen ? { deviceId: { exact: chosen } } : { facingMode: "user" }),
    };
    const stream = await navigator.mediaDevices.getUserMedia({ video: constraints, audio: false });
    video.srcObject = stream;
    await video.play();

    // Some sources report an opaque id rather than a human-readable name.
    const rawLabel = stream.getVideoTracks()[0]?.label || "";
    cameraLabel = rawLabel.length <= 80 ? rawLabel : "";
    populateCameras();

    // Safari and Chrome both report 0x0 for a beat after play() resolves.
    for (let i = 0; i < 40 && video.videoWidth === 0; i++) {
      await new Promise((r) => setTimeout(r, 50));
    }
    if (video.videoWidth === 0) throw new Error("the camera never delivered a frame");

    canvas.width = video.videoWidth || cfg.frameWidth;
    canvas.height = video.videoHeight || cfg.frameHeight;
    darkSince = null;
    camWarning.classList.add("hidden");

    // Build the game state before revealing the stage, so a failure here leaves
    // the admin on the setup screen with a readable message rather than a black
    // canvas hiding it.
    devIndex = 0;
    restart();

    setupEl.classList.add("hidden");
    stageEl.classList.remove("hidden");
    statusEl.textContent = "";

    running = true;
    requestAnimationFrame(loop);
  } catch (err) {
    console.error(err);
    const reasons = {
      NotAllowedError: "Camera permission denied - allow camera access and try again.",
      NotReadableError:
        "Another app or browser tab is using the camera. Close it and try again.",
      OverconstrainedError:
        "That camera is no longer available. Pick a different one and try again.",
      NotFoundError: "No camera found on this device.",
    };
    statusEl.textContent = reasons[err.name] || `Could not start: ${err.message || err}`;
    releaseCamera();
    stageEl.classList.add("hidden");
    setupEl.classList.remove("hidden");
    populateCameras();
  } finally {
    startBtn.disabled = false;
  }
});

function releaseCamera() {
  running = false;
  camWarning.classList.add("hidden");
  darkSince = null;
  if (video.srcObject) {
    for (const track of video.srcObject.getTracks()) track.stop();
    video.srcObject = null;
  }
  if (landmarker) {
    landmarker.close();
    landmarker = null;
  }
}

function exitToSetup() {
  releaseCamera();
  stageEl.classList.add("hidden");
  setupEl.classList.remove("hidden");
}

// --- Controls ---
const hintBtn = document.getElementById("hintBtn");
document.getElementById("infoBtn").addEventListener("click", () => { showInfo = !showInfo; });
hintBtn.addEventListener("click", () => {
  showHint = !showHint;
  hintBtn.classList.toggle("active", showHint);
});
document.getElementById("newCodeBtn").addEventListener("click", restart);
document.getElementById("exitBtn").addEventListener("click", exitToSetup);

window.addEventListener("keydown", (e) => {
  if (!running) return;
  const k = e.key.toLowerCase();
  if (k === "i") showInfo = !showInfo;
  if (k === "h") {
    showHint = !showHint;
    hintBtn.classList.toggle("active", showHint);
  }
  if (k === "r") restart();
});

// --- Main loop ---
function sortedLeftToRight(people, mirror) {
  const displayX = (lm) => {
    const cx = lm.reduce((s, p) => s + p.x, 0) / lm.length;
    return mirror ? 1.0 - cx : cx;
  };
  return [...people].sort((a, b) => displayX(a) - displayX(b));
}

// An exception here would stop the animation callbacks and leave the last
// frame frozen on screen with no explanation, so report it and bail out.
function loop(nowMs) {
  if (!running) return;
  try {
    renderFrame(nowMs);
  } catch (err) {
    console.error(err);
    running = false;
    camWarning.innerHTML =
      `<strong>The trial hit an error and stopped.</strong><br/>` +
      `${err.message || err}<br/>Press Exit and start again.`;
    camWarning.classList.remove("hidden");
    return;
  }
  requestAnimationFrame(loop);
}

function renderFrame(nowMs) {
  const now = nowMs / 1000;
  const w = canvas.width;
  const h = canvas.height;

  checkCameraHealth(now);

  if (video.readyState >= 2 && video.currentTime !== lastVideoTime) {
    lastVideoTime = video.currentTime;
    const result = landmarker.detectForVideo(video, nowMs);
    lastPeople = sortedLeftToRight(result.landmarks || [], cfg.mirrorDisplay);
  }
  const people = lastPeople;

  // Draw the (mirrored) camera frame
  ctx.save();
  if (cfg.mirrorDisplay) {
    ctx.translate(w, 0);
    ctx.scale(-1, 1);
  }
  ctx.drawImage(video, 0, 0, w, h);
  ctx.restore();

  if (state === State.LINEUP) {
    if (people.length >= n) {
      lineupFullSince = lineupFullSince ?? now;
      if (now - lineupFullSince >= cfg.lineupStableSeconds) {
        state = State.DETECTED;
        detectedAt = now;
      }
    } else {
      lineupFullSince = null;
    }
    if (showHint) for (const lm of people) ui.drawSkeleton(ctx, w, h, lm, cfg.mirrorDisplay);
    ui.drawLineup(ctx, w, h, people.length, n);

  } else if (state === State.DETECTED) {
    if (showHint) for (const lm of people) ui.drawSkeleton(ctx, w, h, lm, cfg.mirrorDisplay);
    ui.drawDetected(ctx, w, h, n);
    if (now - detectedAt >= cfg.detectedMessageSeconds) {
      state = State.TRIAL;
      resetTrialState();
    }

  } else if (state === State.TRIAL) {
    const mystery = !dev && cfg.mysteryRounds.includes(roundIdx);
    const statuses = Array(n).fill(false);
    const anchors = [];

    people.slice(0, n).forEach((lm, i) => {
      const letter = code[i];
      const result = POSE_SCORERS[letter](lm, cfg.tuning);
      const threshold = cfg.confidenceOverrides[letter] ?? cfg.confidenceThreshold;
      const held = result.total > threshold;
      const nose = lm[NOSE];
      const x = (cfg.mirrorDisplay ? 1.0 - nose.x : nose.x) * w;

      if (mystery) {
        if (!solved[i] && personClocks[i].update(held, now) >= cfg.holdSeconds) {
          solved[i] = true;
        }
        statuses[i] = solved[i];
        // The skeleton IS the puzzle feedback: always shown
        ui.drawSkeleton(ctx, w, h, lm, cfg.mirrorDisplay, result.parts, threshold);
      } else {
        statuses[i] = held;
        if (showHint) ui.drawSkeleton(ctx, w, h, lm, cfg.mirrorDisplay, result.parts, threshold);
      }
      anchors.push({ letter, ok: statuses[i], x, y: nose.y * h });
    });

    if (mystery) {
      const holdState = (i) =>
        solved[i] || personClocks[i].held <= 0 ? null : cfg.holdSeconds - personClocks[i].held;
      ui.drawStatusCircles(ctx, w, h, solved.map((s, i) => [s, holdState(i)]), cfg.holdSeconds);
      ui.drawPersonCircles(ctx, w, h,
        anchors.map((a, i) => ({ x: a.x, y: a.y, solved: solved[i], remaining: holdState(i) })),
        cfg.holdSeconds);
      if (solved.every(Boolean)) {
        if (roundIdx < rounds.length - 1) {
          state = State.ROUND_COMPLETE;
          roundCompleteAt = now;
        } else {
          state = State.COMPLETE;
          completedAt = now;
        }
      }
    } else {
      const allGreen = people.length >= n && statuses.every(Boolean);
      const elapsed = hold.update(allGreen, now);

      ui.drawPoseCode(ctx, w, h, [...code], statuses);
      ui.drawPersonNames(ctx, w, h, anchors);

      if (elapsed >= cfg.holdSeconds) {
        if (!dev && roundIdx < rounds.length - 1) {
          state = State.ROUND_COMPLETE;
          roundCompleteAt = now;
        } else {
          state = State.COMPLETE;
          completedAt = now;
        }
      } else if (elapsed > 0) {
        ui.drawCountdown(ctx, w, h, cfg.holdSeconds - elapsed, cfg.holdSeconds);
      }
    }

  } else if (state === State.ROUND_COMPLETE) {
    ui.drawRoundComplete(ctx, w, h, roundIdx + 2, cfg.mysteryRounds.includes(roundIdx + 1));
    if (now - roundCompleteAt >= cfg.roundAdvanceSeconds) {
      roundIdx += 1;
      code = nextCode();
      console.log(`Round ${roundIdx + 1} pose code: ${formatCode(code)}`);
      state = State.TRIAL;
      resetTrialState();
    }

  } else if (state === State.COMPLETE) {
    ui.drawComplete(ctx, w, h);
    if (dev && now - completedAt >= cfg.devAdvanceSeconds) {
      code = nextCode();
      console.log(`Dev mode - next pose: ${formatCode(code)}`);
      state = State.TRIAL;
      resetTrialState();
    }
  }

  if (showInfo) {
    ui.drawInfoOverlay(ctx, w, h, cfg.holdSeconds, cfg.confidenceThreshold,
                       rounds, cfg.mysteryRounds);
  } else {
    ui.drawInfoHint(ctx, w, h);
  }
}
