// Central configuration - mirrors pose_trial/config.py in the Python app.
// Every numeric value lives here so each build can be tuned without touching
// the logic. Only `n` (participants) is chosen at runtime by the admin.

export const CONFIG = {
  // --- Gameplay ---
  maxParticipants: 5,
  confidenceThreshold: 0.99,      // pose counts only above this score
  confidenceOverrides: { D: 0.95 }, // per-pose threshold overrides
  holdSeconds: 5.0,               // everyone must hold the pose this long
  // One alphabet per round; the next round unlocks when the mission completes.
  roundAlphabets: ["ABCD", "EFGH", "ABCDEFGH"],
  // Mystery rounds (by index): code hidden; participants follow their skeleton
  // and must hold their found pose for holdSeconds (individual countdowns).
  mysteryRounds: [2],

  // --- Flow timing ---
  lineupStableSeconds: 1.5,       // n people must be seen this long before start
  detectedMessageSeconds: 3.0,    // "Detected n adventurers..." display time
  breakGraceSeconds: 0.1,         // forgive detection flicker shorter than this
  roundAdvanceSeconds: 4.0,       // "round complete" interstitial duration
  devAdvanceSeconds: 3.0,         // dev mode: pause on "complete" before next pose

  // --- Detection ---
  frameWidth: 1280,
  frameHeight: 720,
  minPoseDetectionConfidence: 0.5,
  minPosePresenceConfidence: 0.5,
  minTrackingConfidence: 0.5,
  wasmBaseUrl: "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm",
  modelUrl: "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",

  // --- Display ---
  mirrorDisplay: true,            // selfie view so participants can self-correct

  // --- Pose geometry tolerances (angles in degrees; distances normalized by
  // torso length unless noted). Mirrors PoseTuning in the Python app. ---
  tuning: {
    minVisibility: 0.5,

    // Pose A: crane stance (arms up in a Y, left knee raised and bent)
    aArmAngleIdealLo: 10.0,
    aArmAngleIdealHi: 45.0,
    aArmAngleZero: 70.0,
    aElbowStraightMin: 150.0,
    aElbowStraightZero: 110.0,
    aLegRaiseMin: 0.12,
    aLegRaiseZero: 0.02,
    aKneeBendIdealHi: 120.0,
    aKneeBendZero: 155.0,

    // Pose B: tilted X
    bLeftArmDiagLo: 25.0,
    bLeftArmDiagHi: 65.0,
    bLeftArmDiagZeroLo: 5.0,
    bLeftArmDiagZeroHi: 85.0,
    bRightArmVertHi: 20.0,
    bRightArmVertZero: 45.0,
    bElbowStraightMin: 150.0,
    bElbowStraightZero: 110.0,
    bLegRaiseMin: 0.06,
    bLegRaiseZero: 0.0,

    // Pose C: squat with arms forward
    cKneeBendIdealHi: 130.0,
    cKneeBendZero: 165.0,
    cHipDropIdealHi: 0.45,
    cHipDropZero: 0.75,
    cWristHeightTol: 0.30,
    cWristHeightZero: 0.60,
    cElbowExtendedMin: 120.0,
    cElbowExtendedZero: 80.0,

    // Pose D: frog
    dElbowBendLo: 50.0,
    dElbowBendHi: 120.0,
    dElbowBendZeroLo: 25.0,
    dElbowBendZeroHi: 155.0,
    dWristAboveElbowMin: 0.05,
    dElbowHeightTol: 0.30,
    dElbowHeightZero: 0.55,
    dStanceWidthMin: 1.4,
    dStanceWidthIdeal: 1.8,
    dStanceWidthZero: 1.0,
    dKneeBendIdealHi: 150.0,
    dKneeBendZero: 172.0,

    // Pose E: airplane (arms not scored - figure-skater style)
    eTorsoTiltIdealLo: 50.0,
    eTorsoTiltIdealHi: 100.0,
    eTorsoTiltZeroLo: 25.0,
    eTorsoTiltZeroHi: 125.0,
    eLegRaiseMin: 0.35,
    eLegRaiseZero: 0.10,
    eKneeStraightMin: 150.0,
    eKneeStraightZero: 110.0,

    // Pose F: tree
    fFootToKneeMax: 0.30,
    fFootToKneeZero: 0.60,
    fArmAngleMax: 25.0,
    fArmAngleZero: 50.0,
    fElbowStraightMin: 150.0,
    fElbowStraightZero: 110.0,
    fHandsTogetherMax: 0.25,
    fHandsTogetherZero: 0.50,

    // Pose G: archer (stance normalized by torso length, robust to turning)
    gStraightArmIdealLo: 70.0,
    gStraightArmIdealHi: 110.0,
    gStraightArmZeroLo: 45.0,
    gStraightArmZeroHi: 135.0,
    gStraightElbowMin: 150.0,
    gStraightElbowZero: 110.0,
    gBentElbowLo: 30.0,
    gBentElbowHi: 110.0,
    gBentElbowZeroLo: 10.0,
    gBentElbowZeroHi: 145.0,
    gWristToChinMax: 0.35,
    gWristToChinZero: 0.65,
    gStanceWidthMin: 0.9,
    gStanceWidthZero: 0.5,

    // Pose H: knee hug
    hKneeLiftMin: 0.15,
    hKneeLiftZero: -0.05,
    hKneeBendMax: 90.0,
    hKneeBendZero: 135.0,
    hWristToKneeMax: 0.35,
    hWristToKneeZero: 0.65,
    hStandLegStraightMin: 150.0,
    hStandLegStraightZero: 110.0,
  },
};
