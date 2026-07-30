// Pose scorers - a direct port of pose_trial/poses.py.
// Each scorer takes 33 MediaPipe landmarks and returns { total, parts }:
// total in [0,1] plus a per-body-part breakdown for the hint trace.

// MediaPipe pose landmark indices
export const NOSE = 0;
export const L_SHOULDER = 11, R_SHOULDER = 12;
export const L_ELBOW = 13, R_ELBOW = 14;
export const L_WRIST = 15, R_WRIST = 16;
export const L_HIP = 23, R_HIP = 24;
export const L_KNEE = 25, R_KNEE = 26;
export const L_ANKLE = 27, R_ANKLE = 28;

// Body-part names used in per-part feedback
export const L_ARM = "left_arm", R_ARM = "right_arm";
export const L_LEG = "left_leg", R_LEG = "right_leg";
export const TORSO = "torso";

// What participants actually see and get called. The letters stay as internal
// ids (they key the scorers, the round alphabets and dev mode), but nobody in
// the room should have to remember that "B" means anything. Rename freely: this
// object is the only place the on-screen wording is defined.
export const POSE_NAMES = {
  A: "Crane",
  B: "Star",
  C: "Zombie",
  D: "Frog",
  E: "Rocket",
  F: "Tree",
  G: "Archer",
  H: "Cannonball",
};

// A pose code as the admin reads it in the console: names, with the internal
// ids kept alongside so dev mode stays debuggable.
export function formatCode(code) {
  return `${[...code].map((c) => POSE_NAMES[c]).join(" ")}  [${code}]`;
}

export const POSE_DESCRIPTIONS = {
  A: "Crane: both arms reaching straight up to the sky, left knee raised and bent",
  B: "Star: left arm on a diagonal, right arm straight up, right leg raised",
  C: "Zombie: squat down with both arms reaching forward",
  D: "Frog: crouch all the way down, knees pushed out, hands to the floor",
  E: "Rocket: one arm straight up, the other pressed down at your side, feet together",
  F: "Tree: one foot on the other knee, arms overhead with hands together",
  G: "Archer: aim your bow arm at the sky, other elbow bent pulling to the " +
     "chin, one leg lifted",
  H: "Cannonball: pull one knee to your chest with both hands",
};

class Criteria {
  constructor() { this.items = []; }
  add(part, score) { this.items.push([part, score]); }
  total() {
    return this.items.reduce((s, [, v]) => s + v, 0) / this.items.length;
  }
  result() {
    const byPart = {};
    for (const [part, score] of this.items) {
      (byPart[part] ??= []).push(score);
    }
    const parts = {};
    for (const [part, scores] of Object.entries(byPart)) {
      parts[part] = scores.reduce((a, b) => a + b, 0) / scores.length;
    }
    return { total: this.total(), parts };
  }
}

const FAIL = { total: 0.0, parts: {} };

function trapezoid(value, zeroLo, oneLo, oneHi, zeroHi) {
  if (value <= zeroLo || value >= zeroHi) return 0.0;
  if (value >= oneLo && value <= oneHi) return 1.0;
  if (value < oneLo) return (value - zeroLo) / (oneLo - zeroLo);
  return (zeroHi - value) / (zeroHi - oneHi);
}

function atLeast(value, zero, one) {
  if (zero === one) return value >= one ? 1.0 : 0.0;
  return Math.max(0.0, Math.min(1.0, (value - zero) / (one - zero)));
}

function atMost(value, one, zero) {
  return atLeast(-value, -zero, -one);
}

function dist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function angleDeg(a, b, c) {
  const v1 = [a.x - b.x, a.y - b.y];
  const v2 = [c.x - b.x, c.y - b.y];
  const n1 = Math.hypot(...v1);
  const n2 = Math.hypot(...v2);
  if (n1 < 1e-6 || n2 < 1e-6) return 0.0;
  const cos = Math.max(-1, Math.min(1, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)));
  return (Math.acos(cos) * 180) / Math.PI;
}

function angleFromVerticalUp(origin, tip) {
  const dx = tip.x - origin.x;
  const dy = tip.y - origin.y; // y points down
  const n = Math.hypot(dx, dy);
  if (n < 1e-6) return 180.0;
  const cos = Math.max(-1, Math.min(1, -dy / n));
  return (Math.acos(cos) * 180) / Math.PI;
}

function torsoLength(lm) {
  const sx = (lm[L_SHOULDER].x + lm[R_SHOULDER].x) / 2;
  const sy = (lm[L_SHOULDER].y + lm[R_SHOULDER].y) / 2;
  const hx = (lm[L_HIP].x + lm[R_HIP].x) / 2;
  const hy = (lm[L_HIP].y + lm[R_HIP].y) / 2;
  return Math.max(1e-6, Math.hypot(sx - hx, sy - hy));
}

function visibilityOk(lm, indices, t) {
  const vis = indices.map((i) => lm[i].visibility ?? 1.0);
  return vis.reduce((a, b) => a + b, 0) / vis.length >= t.minVisibility;
}

const ARMS = [
  [L_ARM, L_SHOULDER, L_ELBOW, L_WRIST],
  [R_ARM, R_SHOULDER, R_ELBOW, R_WRIST],
];
const LEGS = [
  [L_LEG, L_HIP, L_KNEE, L_ANKLE],
  [R_LEG, R_HIP, R_KNEE, R_ANKLE],
];

function scorePoseA(lm, t) {
  const needed = [NOSE, L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST,
                  L_HIP, L_KNEE, L_ANKLE, R_ANKLE];
  if (!visibilityOk(lm, needed, t)) return FAIL;

  const torso = torsoLength(lm);
  const c = new Criteria();
  for (const [part, sh, el, wr] of ARMS) {
    const angle = angleFromVerticalUp(lm[sh], lm[wr]);
    c.add(part, atMost(angle, t.aArmAngleMax, t.aArmAngleZero));
    const above = (lm[NOSE].y - lm[wr].y) / torso;
    c.add(part, atLeast(above, t.aWristAboveHeadZero, t.aWristAboveHeadMin));
    const elbow = angleDeg(lm[sh], lm[el], lm[wr]);
    c.add(part, atLeast(elbow, t.aElbowStraightZero, t.aElbowStraightMin));
  }

  const apart = atLeast(dist(lm[L_WRIST], lm[R_WRIST]) / torso,
                        t.aHandsApartZero, t.aHandsApartMin);
  c.add(L_ARM, apart);
  c.add(R_ARM, apart);

  const legRaise = (lm[R_ANKLE].y - lm[L_ANKLE].y) / torso; // + = left ankle higher
  c.add(L_LEG, atLeast(legRaise, t.aLegRaiseZero, t.aLegRaiseMin));

  const kneeAngle = angleDeg(lm[L_HIP], lm[L_KNEE], lm[L_ANKLE]);
  c.add(L_LEG, trapezoid(kneeAngle, -1.0, 0.0, t.aKneeBendIdealHi, t.aKneeBendZero));

  return c.result();
}

function scorePoseB(lm, t) {
  const needed = [NOSE, L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST,
                  L_ANKLE, R_ANKLE];
  if (!visibilityOk(lm, needed, t)) return FAIL;

  const c = new Criteria();

  const leftArm = angleFromVerticalUp(lm[L_SHOULDER], lm[L_WRIST]);
  c.add(L_ARM, trapezoid(leftArm, t.bLeftArmDiagZeroLo, t.bLeftArmDiagLo,
                         t.bLeftArmDiagHi, t.bLeftArmDiagZeroHi));

  const rightArm = angleFromVerticalUp(lm[R_SHOULDER], lm[R_WRIST]);
  c.add(R_ARM, trapezoid(rightArm, -1.0, 0.0, t.bRightArmVertHi, t.bRightArmVertZero));

  for (const [part, sh, el, wr] of ARMS) {
    const elbow = angleDeg(lm[sh], lm[el], lm[wr]);
    c.add(part, atLeast(elbow, t.bElbowStraightZero, t.bElbowStraightMin));
  }

  const torso = torsoLength(lm);

  // "Straight up" means the hand clears the head. Free for anyone actually
  // reaching up, and it keeps a hand held at the chin (pose G) out of B.
  const above = (lm[NOSE].y - lm[R_WRIST].y) / torso;
  c.add(R_ARM, atLeast(above, t.bRightWristAboveNoseZero, t.bRightWristAboveNoseMin));

  const apart = atLeast(dist(lm[L_WRIST], lm[R_WRIST]) / torso,
                        t.bWristsApartZero, t.bWristsApartMin);
  c.add(L_ARM, apart);
  c.add(R_ARM, apart);

  const legRaise = (lm[L_ANKLE].y - lm[R_ANKLE].y) / torso; // + = right ankle higher
  c.add(R_LEG, atLeast(legRaise, t.bLegRaiseZero, t.bLegRaiseMin));

  return c.result();
}

function scorePoseC(lm, t) {
  const needed = [L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST,
                  L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE];
  if (!visibilityOk(lm, needed, t)) return FAIL;

  const torso = torsoLength(lm);
  const c = new Criteria();

  for (const [part, hip, knee, ankle] of LEGS) {
    const kneeAngle = angleDeg(lm[hip], lm[knee], lm[ankle]);
    c.add(part, trapezoid(kneeAngle, -1.0, 0.0, t.cKneeBendIdealHi, t.cKneeBendZero));
  }

  const hipY = (lm[L_HIP].y + lm[R_HIP].y) / 2;
  // The LOWER knee, not the average: with one knee lifted (the knee hug, H)
  // the average sits at hip level and fakes a deep squat.
  const kneeY = Math.max(lm[L_KNEE].y, lm[R_KNEE].y);
  const hipDrop = (kneeY - hipY) / torso;
  c.add(TORSO, trapezoid(hipDrop, -1.0, -0.5, t.cHipDropIdealHi, t.cHipDropZero));

  for (const [part, sh, el, wr] of ARMS) {
    const wristHeight = Math.abs(lm[wr].y - lm[sh].y) / torso;
    c.add(part, trapezoid(wristHeight, -1.0, 0.0, t.cWristHeightTol, t.cWristHeightZero));
    const elbow = angleDeg(lm[sh], lm[el], lm[wr]);
    c.add(part, atLeast(elbow, t.cElbowExtendedZero, t.cElbowExtendedMin));
  }

  return c.result();
}

function scorePoseD(lm, t) {
  const needed = [L_SHOULDER, R_SHOULDER, L_WRIST, R_WRIST,
                  L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE];
  if (!visibilityOk(lm, needed, t)) return FAIL;

  const torso = torsoLength(lm);
  const c = new Criteria();

  for (const [part, hip, knee, ankle] of LEGS) {
    const kneeAngle = angleDeg(lm[hip], lm[knee], lm[ankle]);
    c.add(part, trapezoid(kneeAngle, -1.0, 0.0, t.dKneeBendIdealHi, t.dKneeBendZero));
  }

  const hipY = (lm[L_HIP].y + lm[R_HIP].y) / 2;
  const kneeY = (lm[L_KNEE].y + lm[R_KNEE].y) / 2;
  c.add(TORSO, trapezoid((kneeY - hipY) / torso, -1.0, -0.5, t.dHipDropIdealHi, t.dHipDropZero));

  for (const [part, wr, knee] of [[L_ARM, L_WRIST, L_KNEE], [R_ARM, R_WRIST, R_KNEE]]) {
    const reach = (lm[wr].y - lm[knee].y) / torso; // + = hand below the knee
    c.add(part, atLeast(reach, t.dHandsBelowKneeZero, t.dHandsBelowKneeMin));
  }

  const kneeW = Math.abs(lm[L_KNEE].x - lm[R_KNEE].x);
  const ankleW = Math.abs(lm[L_ANKLE].x - lm[R_ANKLE].x);
  const kneesOut = atLeast((kneeW - ankleW) / torso, t.dKneesOutZero, t.dKneesOutMin);
  c.add(L_LEG, kneesOut);
  c.add(R_LEG, kneesOut);

  return c.result();
}

function scorePoseE(lm, t) {
  const needed = [NOSE, L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST,
                  L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE];
  if (!visibilityOk(lm, needed, t)) return FAIL;

  const torso = torsoLength(lm);

  const feet = Math.abs(lm[L_ANKLE].x - lm[R_ANKLE].x) / torso;
  const feetScore = atMost(feet, t.eFeetTogetherMax, t.eFeetTogetherZero);

  const options = [];
  for (const [up, down] of [[ARMS[0], ARMS[1]], [ARMS[1], ARMS[0]]]) {
    const [uPart, uSh, , uWr] = up;
    const [dPart, dSh, , dWr] = down;
    const c = new Criteria();

    const upAngle = angleFromVerticalUp(lm[uSh], lm[uWr]);
    c.add(uPart, atMost(upAngle, t.eUpArmAngleMax, t.eUpArmAngleZero));
    const overhead = (lm[NOSE].y - lm[uWr].y) / torso; // + = wrist above the head
    c.add(uPart, atLeast(overhead, t.eUpWristAboveHeadZero, t.eUpWristAboveHeadMin));

    const downAngle = angleFromVerticalUp(lm[dSh], lm[dWr]);
    c.add(dPart, atLeast(downAngle, t.eDownArmAngleZero, t.eDownArmAngleMin));
    const dHip = dPart === L_ARM ? lm[L_HIP] : lm[R_HIP];
    const pinned = dist(lm[dWr], dHip) / torso;
    c.add(dPart, atMost(pinned, t.eDownWristToHipMax, t.eDownWristToHipZero));

    for (const [part, sh, el, wr] of [up, down]) {
      const elbow = angleDeg(lm[sh], lm[el], lm[wr]);
      c.add(part, atLeast(elbow, t.eElbowStraightZero, t.eElbowStraightMin));
    }

    for (const [part, hip, knee, ankle] of LEGS) {
      c.add(part, feetScore);
      const kneeAngle = angleDeg(lm[hip], lm[knee], lm[ankle]);
      c.add(part, atLeast(kneeAngle, t.eLegStraightZero, t.eLegStraightMin));
    }

    options.push(c);
  }

  return options.reduce((a, b) => (a.total() >= b.total() ? a : b)).result();
}

function scorePoseF(lm, t) {
  const needed = [L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST,
                  L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE];
  if (!visibilityOk(lm, needed, t)) return FAIL;

  const torso = torsoLength(lm);
  const c = new Criteria();

  const leftFoot = dist(lm[L_ANKLE], lm[R_KNEE]) / torso;
  const rightFoot = dist(lm[R_ANKLE], lm[L_KNEE]) / torso;
  const raisedPart = leftFoot <= rightFoot ? L_LEG : R_LEG;
  c.add(raisedPart, atMost(Math.min(leftFoot, rightFoot), t.fFootToKneeMax, t.fFootToKneeZero));

  for (const [part, sh, el, wr] of ARMS) {
    const armAngle = angleFromVerticalUp(lm[sh], lm[wr]);
    c.add(part, atMost(armAngle, t.fArmAngleMax, t.fArmAngleZero));
    const elbow = angleDeg(lm[sh], lm[el], lm[wr]);
    c.add(part, atLeast(elbow, t.fElbowStraightZero, t.fElbowStraightMin));
  }

  const hands = atMost(dist(lm[L_WRIST], lm[R_WRIST]) / torso,
                       t.fHandsTogetherMax, t.fHandsTogetherZero);
  c.add(L_ARM, hands);
  c.add(R_ARM, hands);

  return c.result();
}

// Archer: the bow arm points up on a diagonal rather than out to the side,
// which keeps the pose narrow. Either arm may draw, either leg may lift.
function scorePoseG(lm, t) {
  const needed = [NOSE, L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST,
                  L_ANKLE, R_ANKLE];
  if (!visibilityOk(lm, needed, t)) return FAIL;

  const torso = torsoLength(lm);

  // Either foot may be the raised one.
  const lift = Math.abs(lm[L_ANKLE].y - lm[R_ANKLE].y) / torso;
  const liftScore = atLeast(lift, t.gLegLiftZero, t.gLegLiftMin);

  const options = [];
  for (const [straight, bent] of [[ARMS[0], ARMS[1]], [ARMS[1], ARMS[0]]]) {
    const [sPart, sSh, sEl, sWr] = straight;
    const [bPart, bSh, bEl, bWr] = bent;
    const c = new Criteria();

    const armAngle = angleFromVerticalUp(lm[sSh], lm[sWr]);
    c.add(sPart, trapezoid(armAngle, t.gBowArmZeroLo, t.gBowArmIdealLo,
                           t.gBowArmIdealHi, t.gBowArmZeroHi));
    const elbow = angleDeg(lm[sSh], lm[sEl], lm[sWr]);
    c.add(sPart, atLeast(elbow, t.gStraightElbowZero, t.gStraightElbowMin));
    // The bow hand reaches away - it is not a second fist at the chin.
    const reach = dist(lm[sWr], lm[NOSE]) / torso;
    c.add(sPart, atLeast(reach, t.gBowWristFromFaceZero, t.gBowWristFromFaceMin));

    const bentAngle = angleDeg(lm[bSh], lm[bEl], lm[bWr]);
    c.add(bPart, trapezoid(bentAngle, t.gBentElbowZeroLo, t.gBentElbowLo,
                           t.gBentElbowHi, t.gBentElbowZeroHi));
    const chin = dist(lm[bWr], lm[NOSE]) / torso;
    c.add(bPart, atMost(chin, t.gWristToChinMax, t.gWristToChinZero));

    c.add(L_LEG, liftScore);
    c.add(R_LEG, liftScore);

    options.push(c);
  }

  return options.reduce((a, b) => (a.total() >= b.total() ? a : b)).result();
}

function scorePoseH(lm, t) {
  const needed = [L_WRIST, R_WRIST, L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE];
  if (!visibilityOk(lm, needed, t)) return FAIL;

  const torso = torsoLength(lm);

  const options = [];
  for (const [raised, standing] of [[LEGS[0], LEGS[1]], [LEGS[1], LEGS[0]]]) {
    const [part, hip, knee, ankle] = raised;
    const [oPart, oHip, oKnee, oAnkle] = standing;
    const c = new Criteria();

    const lift = (lm[hip].y - lm[knee].y) / torso;
    c.add(part, atLeast(lift, t.hKneeLiftZero, t.hKneeLiftMin));
    const kneeAngle = angleDeg(lm[hip], lm[knee], lm[ankle]);
    c.add(part, atMost(kneeAngle, t.hKneeBendMax, t.hKneeBendZero));

    for (const [aPart, wr] of [[L_ARM, L_WRIST], [R_ARM, R_WRIST]]) {
      const hug = dist(lm[wr], lm[knee]) / torso;
      c.add(aPart, atMost(hug, t.hWristToKneeMax, t.hWristToKneeZero));
    }

    const standAngle = angleDeg(lm[oHip], lm[oKnee], lm[oAnkle]);
    c.add(oPart, atLeast(standAngle, t.hStandLegStraightZero, t.hStandLegStraightMin));

    options.push(c);
  }

  return options.reduce((a, b) => (a.total() >= b.total() ? a : b)).result();
}

export const POSE_SCORERS = {
  A: scorePoseA,
  B: scorePoseB,
  C: scorePoseC,
  D: scorePoseD,
  E: scorePoseE,
  F: scorePoseF,
  G: scorePoseG,
  H: scorePoseH,
};
