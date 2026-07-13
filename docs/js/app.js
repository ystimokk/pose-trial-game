// Main application - a port of pose_trial/app.py.
// States: LINEUP -> DETECTED -> TRIAL (per round) -> ROUND_COMPLETE -> COMPLETE

import { PoseLandmarker, FilesetResolver } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/vision_bundle.mjs";
import { CONFIG } from "./config.js";
import { POSE_SCORERS, NOSE } from "./poses.js";
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

// --- Game state ---
let landmarker = null;
let running = false;
let n = 2;
let dev = false;
let initialRoundIdx = 0;

let state, code, roundIdx, devIndex;
let lineupFullSince, detectedAt, holdStartedAt, lastAllGreenAt, completedAt, roundCompleteAt;
let solved, personHold, personGreen;
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

function resetTrialState() {
  holdStartedAt = null;
  lastAllGreenAt = null;
  solved = Array(n).fill(false);
  personHold = Array(n).fill(null);
  personGreen = Array(n).fill(null);
}

function restart() {
  roundIdx = initialRoundIdx;
  code = nextCode();
  console.log(`Pose code: ${code}`);
  state = dev ? State.TRIAL : State.LINEUP;
  lineupFullSince = null;
  resetTrialState();
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
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: cfg.frameWidth, height: cfg.frameHeight, facingMode: "user" },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();

    canvas.width = video.videoWidth || cfg.frameWidth;
    canvas.height = video.videoHeight || cfg.frameHeight;

    setupEl.classList.add("hidden");
    stageEl.classList.remove("hidden");
    statusEl.textContent = "";

    restart();
    running = true;
    requestAnimationFrame(loop);
  } catch (err) {
    console.error(err);
    statusEl.textContent =
      err.name === "NotAllowedError"
        ? "Camera permission denied - allow camera access and try again."
        : `Could not start: ${err.message || err}`;
  } finally {
    startBtn.disabled = false;
  }
});

function exitToSetup() {
  running = false;
  if (video.srcObject) {
    for (const track of video.srcObject.getTracks()) track.stop();
    video.srcObject = null;
  }
  if (landmarker) {
    landmarker.close();
    landmarker = null;
  }
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

function loop(nowMs) {
  if (!running) return;
  const now = nowMs / 1000;
  const w = canvas.width;
  const h = canvas.height;

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
        if (!solved[i]) {
          if (held) {
            personGreen[i] = now;
            personHold[i] = personHold[i] ?? now;
            if (now - personHold[i] >= cfg.holdSeconds) solved[i] = true;
          } else if (personGreen[i] === null || now - personGreen[i] > cfg.breakGraceSeconds) {
            personHold[i] = null;
          }
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
        solved[i] || personHold[i] === null ? null : cfg.holdSeconds - (now - personHold[i]);
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
      if (allGreen) {
        lastAllGreenAt = now;
        holdStartedAt = holdStartedAt ?? now;
      } else if (lastAllGreenAt === null || now - lastAllGreenAt > cfg.breakGraceSeconds) {
        holdStartedAt = null;
      }

      ui.drawPoseCode(ctx, w, h, [...code], statuses);
      ui.drawPersonLetters(ctx, w, h, anchors);

      if (holdStartedAt !== null) {
        const elapsed = now - holdStartedAt;
        if (elapsed >= cfg.holdSeconds) {
          if (!dev && roundIdx < rounds.length - 1) {
            state = State.ROUND_COMPLETE;
            roundCompleteAt = now;
          } else {
            state = State.COMPLETE;
            completedAt = now;
          }
        } else {
          ui.drawCountdown(ctx, w, h, cfg.holdSeconds - elapsed, cfg.holdSeconds);
        }
      }
    }

  } else if (state === State.ROUND_COMPLETE) {
    ui.drawRoundComplete(ctx, w, h, roundIdx + 2, cfg.mysteryRounds.includes(roundIdx + 1));
    if (now - roundCompleteAt >= cfg.roundAdvanceSeconds) {
      roundIdx += 1;
      code = nextCode();
      console.log(`Round ${roundIdx + 1} pose code: ${code}`);
      state = State.TRIAL;
      resetTrialState();
    }

  } else if (state === State.COMPLETE) {
    ui.drawComplete(ctx, w, h);
    if (dev && now - completedAt >= cfg.devAdvanceSeconds) {
      code = nextCode();
      console.log(`Dev mode - next pose code: ${code}`);
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

  requestAnimationFrame(loop);
}
