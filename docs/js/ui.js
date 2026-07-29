// Canvas rendering - a port of pose_trial/ui.py.
// No bounding boxes, no confidence numbers: participants only see their
// letter/circle, green when the pose is held well enough, dark red otherwise.

export const GREEN = "rgb(80, 220, 80)";
export const DARK_RED = "rgb(170, 40, 40)";
export const WHITE = "rgb(245, 245, 245)";
export const ACCENT = "rgb(80, 200, 255)";
export const PANEL = "rgb(12, 16, 20)";
export const NEUTRAL = "rgb(200, 200, 200)";

const FONT = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif";

function text(ctx, str, x, y, px, color, { weight = 700, align = "center", alpha = 1 } = {}) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.font = `${weight} ${Math.round(px)}px ${FONT}`;
  ctx.fillStyle = color;
  ctx.textAlign = align;
  ctx.textBaseline = "middle";
  ctx.fillText(str, x, y);
  ctx.restore();
}

function dimPanel(ctx, w, y0, y1, alpha = 0.55) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.fillStyle = PANEL;
  ctx.fillRect(0, y0, w, y1 - y0);
  ctx.restore();
}

export function drawBanner(ctx, w, h, title, subtitle) {
  dimPanel(ctx, w, h * 0.32, h * 0.58);
  text(ctx, title, w / 2, h * 0.42, h * 0.065, WHITE);
  if (subtitle) text(ctx, subtitle, w / 2, h * 0.52, h * 0.034, ACCENT, { weight: 600 });
}

export function drawLineup(ctx, w, h, detected, n) {
  drawBanner(ctx, w, h, "Adventurers, line up!",
             `Waiting for ${n} adventurer${n > 1 ? "s" : ""}... (${detected} in view)`);
}

export function drawDetected(ctx, w, h, n) {
  drawBanner(ctx, w, h, `Detected ${n} adventurer${n > 1 ? "s" : ""}...`, "Starting the trial.");
}

export function drawPoseCode(ctx, w, h, letters, statuses) {
  const stripH = h * 0.17;
  dimPanel(ctx, w, 0, stripH, 0.6);

  const n = letters.length;
  const slot = w / (n + 1);
  letters.forEach((letter, i) => {
    text(ctx, letter, slot * (i + 1), stripH * 0.52, stripH * 0.62,
         statuses[i] ? GREEN : DARK_RED, { weight: 800 });
  });
}

export function drawPersonLetters(ctx, w, h, anchors) {
  for (const { letter, ok, x, y } of anchors) {
    text(ctx, letter, x, Math.max(40, y - 60), h * 0.075,
         ok ? GREEN : DARK_RED, { weight: 800 });
  }
}

// --- Mystery round markers ---

function countdownNumber(remaining, total) {
  let number = Math.ceil(remaining);
  number = Math.max(1, Math.min(Math.floor(total), number));
  const progress = 1.0 - (remaining - (number - 1)); // 0 -> 1 within this second
  let alpha;
  if (progress < 0.15) alpha = progress / 0.15;
  else if (progress > 0.65) alpha = Math.max(0, (1.0 - progress) / 0.35);
  else alpha = 1.0;
  return { number, alpha, progress };
}

function circle(ctx, x, y, r, color) {
  ctx.save();
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

export function drawStatusCircles(ctx, w, h, states, totalSeconds) {
  const stripH = h * 0.17;
  dimPanel(ctx, w, 0, stripH, 0.6);

  const n = states.length;
  const slot = w / (n + 1);
  const radius = stripH * 0.3;
  states.forEach(([solved, remaining], i) => {
    const cx = slot * (i + 1);
    const cy = stripH * 0.5;
    if (solved) {
      circle(ctx, cx, cy, radius, GREEN);
    } else if (remaining != null) {
      const { number, alpha } = countdownNumber(remaining, totalSeconds);
      text(ctx, String(number), cx, cy, stripH * 0.62, GREEN, { weight: 800, alpha });
    } else {
      circle(ctx, cx, cy, radius, DARK_RED);
    }
  });
}

export function drawPersonCircles(ctx, w, h, markers, totalSeconds) {
  for (const { x, y, solved, remaining } of markers) {
    const cx = x;
    const cy = Math.max(40, y - 70);
    if (solved) {
      circle(ctx, cx, cy, 22, GREEN);
    } else if (remaining != null) {
      const { number, alpha } = countdownNumber(remaining, totalSeconds);
      text(ctx, String(number), cx, cy, h * 0.065, GREEN, { weight: 800, alpha });
    } else {
      circle(ctx, cx, cy, 22, DARK_RED);
    }
  }
}

export function drawCountdown(ctx, w, h, remaining, total) {
  const { number, alpha, progress } = countdownNumber(remaining, total);
  const px = h * (0.28 + 0.07 * progress); // gently grows as it fades
  text(ctx, String(number), w / 2, h / 2, px, WHITE, { weight: 800, alpha: alpha * 0.9 });
  text(ctx, "HOLD THE POSE", w / 2, h * 0.82, h * 0.04, ACCENT, { weight: 700 });
}

export function drawComplete(ctx, w, h) {
  ctx.save();
  ctx.globalAlpha = 0.65;
  ctx.fillStyle = PANEL;
  ctx.fillRect(0, 0, w, h);
  ctx.restore();
  text(ctx, "MISSION COMPLETE", w / 2, h * 0.42, h * 0.09, GREEN, { weight: 800 });
  text(ctx, "Adventurers have mastered the required skill", w / 2, h * 0.55, h * 0.04, WHITE);
  text(ctx, "Press R for a new trial", w / 2, h * 0.88, h * 0.028, ACCENT);
}

export function drawRoundComplete(ctx, w, h, nextRound, mystery) {
  if (mystery) {
    drawBanner(ctx, w, h, "Skill mastered!",
               "Final round: your pose is a MYSTERY. Follow your skeleton and hold it!");
  } else {
    drawBanner(ctx, w, h, "Skill mastered!",
               `But the trial is not over... Round ${nextRound} begins. Get ready!`);
  }
}

// --- Skeleton trace (hint mode / mystery round) ---

const PART_SEGMENTS = {
  left_arm: [[11, 13], [13, 15]],
  right_arm: [[12, 14], [14, 16]],
  torso: [[11, 12], [11, 23], [12, 24], [23, 24]],
  left_leg: [[23, 25], [25, 27]],
  right_leg: [[24, 26], [26, 28]],
};

export function drawSkeleton(ctx, w, h, landmarks, mirror, partScores = null, threshold = 1.0) {
  const pt = (i) => {
    const x = mirror ? 1.0 - landmarks[i].x : landmarks[i].x;
    return [x * w, landmarks[i].y * h];
  };

  ctx.save();
  ctx.lineWidth = 3;
  ctx.lineCap = "round";
  for (const [part, segments] of Object.entries(PART_SEGMENTS)) {
    let color = NEUTRAL;
    if (partScores !== null && part in partScores) {
      color = partScores[part] >= threshold ? GREEN : DARK_RED;
    }
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    const joints = new Set();
    for (const [a, b] of segments) {
      const [x1, y1] = pt(a);
      const [x2, y2] = pt(b);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      joints.add(a); joints.add(b);
    }
    for (const i of joints) {
      const [x, y] = pt(i);
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.restore();
}

export function drawInfoHint(ctx, w, h) {
  text(ctx, "Press I for how to play - H for hint trace", 18, h - 24, h * 0.026, ACCENT,
       { weight: 600, align: "left" });
}

// --- Info overlay with stick-figure pose cards ---

const POSE_FIGURES = {
  A: {
    head: [0.5, 0.20],
    lines: [
      [[0.5, 0.28], [0.5, 0.60]],
      [[0.58, 0.33], [0.62, 0.02]],
      [[0.42, 0.33], [0.38, 0.02]],
      [[0.5, 0.60], [0.48, 0.94]],
      [[0.5, 0.60], [0.64, 0.66]],
      [[0.64, 0.66], [0.58, 0.80]],
    ],
  },
  B: {
    head: [0.5, 0.12],
    lines: [
      [[0.5, 0.20], [0.5, 0.55]],
      [[0.44, 0.25], [0.30, 0.04]],
      [[0.58, 0.25], [0.60, 0.00]],
      [[0.5, 0.55], [0.44, 0.92]],
      [[0.5, 0.55], [0.60, 0.72]],
      [[0.60, 0.72], [0.58, 0.86]],
    ],
  },
  C: {
    head: [0.40, 0.30],
    lines: [
      [[0.40, 0.38], [0.42, 0.62]],
      [[0.40, 0.42], [0.74, 0.40]],
      [[0.40, 0.46], [0.74, 0.46]],
      [[0.42, 0.62], [0.62, 0.66]],
      [[0.62, 0.66], [0.58, 0.92]],
      [[0.42, 0.62], [0.56, 0.70]],
      [[0.56, 0.70], [0.52, 0.92]],
    ],
  },
  D: {
    head: [0.5, 0.30],
    lines: [
      [[0.5, 0.38], [0.5, 0.62]],
      [[0.44, 0.42], [0.40, 0.62]],
      [[0.40, 0.62], [0.46, 0.88]],
      [[0.56, 0.42], [0.60, 0.62]],
      [[0.60, 0.62], [0.54, 0.88]],
      [[0.5, 0.62], [0.28, 0.70]],
      [[0.28, 0.70], [0.38, 0.92]],
      [[0.5, 0.62], [0.72, 0.70]],
      [[0.72, 0.70], [0.62, 0.92]],
    ],
  },
  E: {
    head: [0.5, 0.12],
    lines: [
      [[0.5, 0.20], [0.5, 0.55]],
      [[0.58, 0.25], [0.62, 0.00]],
      [[0.42, 0.25], [0.38, 0.58]],
      [[0.5, 0.55], [0.47, 0.92]],
      [[0.5, 0.55], [0.53, 0.92]],
    ],
  },
  F: {
    head: [0.5, 0.12],
    lines: [
      [[0.5, 0.20], [0.5, 0.55]],
      [[0.44, 0.24], [0.49, 0.02]],
      [[0.56, 0.24], [0.51, 0.02]],
      [[0.5, 0.55], [0.5, 0.92]],
      [[0.5, 0.55], [0.68, 0.62]],
      [[0.68, 0.62], [0.53, 0.72]],
    ],
  },
  G: {
    head: [0.5, 0.16],
    lines: [
      [[0.5, 0.24], [0.5, 0.56]],
      [[0.56, 0.28], [0.72, 0.02]],
      [[0.44, 0.28], [0.34, 0.20]],
      [[0.34, 0.20], [0.46, 0.24]],
      [[0.5, 0.56], [0.44, 0.92]],
      [[0.5, 0.56], [0.63, 0.70]],
      [[0.63, 0.70], [0.59, 0.81]],
    ],
  },
  H: {
    head: [0.5, 0.12],
    lines: [
      [[0.5, 0.20], [0.5, 0.55]],
      [[0.5, 0.55], [0.5, 0.92]],
      [[0.5, 0.55], [0.66, 0.42]],
      [[0.66, 0.42], [0.64, 0.58]],
      [[0.44, 0.26], [0.62, 0.40]],
      [[0.56, 0.26], [0.66, 0.44]],
    ],
  },
};

const POSE_CAPTIONS = {
  A: "Crane: both arms to the sky, left knee up",
  B: "Tilted X, right leg up",
  C: "Squat, arms forward",
  D: "Frog: crouch low, hands down",
  E: "Rocket: one arm up, one arm down",
  F: "Tree: foot on knee, hands up",
  G: "Archer: aim at the sky, one leg up",
  H: "Knee hug: knee to chest",
};

function stickFigure(ctx, letter, x0, y0, size, color) {
  const fig = POSE_FIGURES[letter];
  const thickness = Math.max(2, size * 0.035);
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = thickness;
  ctx.lineCap = "round";

  const [hx, hy] = fig.head;
  ctx.beginPath();
  ctx.arc(x0 + hx * size, y0 + hy * size, Math.max(3, size * 0.08), 0, Math.PI * 2);
  ctx.stroke();

  for (const [[x1, y1], [x2, y2]] of fig.lines) {
    ctx.beginPath();
    ctx.moveTo(x0 + x1 * size, y0 + y1 * size);
    ctx.lineTo(x0 + x2 * size, y0 + y2 * size);
    ctx.stroke();
  }
  ctx.restore();
}

export function drawInfoOverlay(ctx, w, h, holdSeconds, confidenceThreshold, rounds, mysteryRounds) {
  ctx.save();
  ctx.globalAlpha = 0.88;
  ctx.fillStyle = PANEL;
  ctx.fillRect(0, 0, w, h);
  ctx.restore();

  text(ctx, "HOW TO PLAY", w / 2, h * 0.055, h * 0.05, ACCENT, { weight: 800 });

  const rules = [
    "1. Line up left to right - each adventurer gets one letter",
    "2. Do your letter's pose until it turns GREEN",
    `3. When ALL letters are green, hold together for ${holdSeconds} seconds`,
    "4. Round 1 done? Harder poses unlock... and the final round is a MYSTERY:",
    `no letter, just your glowing skeleton - find your secret pose and hold it ${holdSeconds}s to lock in!`,
    `(The AI must be more than ${Math.round(confidenceThreshold * 100)}% sure your pose is right)`,
  ];
  let y = h * 0.105;
  for (const line of rules) {
    text(ctx, line, w / 2, y, h * 0.026, WHITE, { weight: 600 });
    y += h * 0.038;
  }

  const mysterySet = new Set(mysteryRounds);
  const visibleRounds = rounds.filter((_, i) => !mysterySet.has(i));

  const nCols = Math.max(...visibleRounds.map((r) => r.length));
  const cardW = w / (nCols + 1.6);
  const gap = (w - nCols * cardW) / (nCols + 1);
  const rowH = h * 0.31;
  const cardSize = Math.min(cardW * 0.72, rowH * 0.62);
  const top0 = h * 0.335;

  visibleRounds.forEach((letters, row) => {
    const top = top0 + row * rowH;
    text(ctx, `ROUND ${row + 1}`, gap * 0.4, top + rowH * 0.5, h * 0.026, ACCENT,
         { weight: 700, align: "left" });
    [...letters].forEach((letter, i) => {
      const x0 = gap + i * (cardW + gap);
      text(ctx, letter, x0 + cardW / 2, top + h * 0.02, h * 0.042, GREEN, { weight: 800 });
      stickFigure(ctx, letter, x0 + (cardW - cardSize) / 2, top + h * 0.05, cardSize, WHITE);
      text(ctx, POSE_CAPTIONS[letter], x0 + cardW / 2,
           top + h * 0.055 + cardSize + h * 0.025, h * 0.021, ACCENT, { weight: 600 });
    });
  });

  text(ctx, "Press I to close", w / 2, h * 0.97, h * 0.026, WHITE, { weight: 600 });
}
