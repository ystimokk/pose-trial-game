// Central configuration - mirrors pose_trial/config.py in the Python app.
// Every numeric value lives here so each build can be tuned without touching
// the logic. Only `n` (participants) is chosen at runtime by the admin.

export const CONFIG = {
  // --- Gameplay ---
  maxParticipants: 5,
  // Pose counts only above this score. Kept forgiving for kids: combined with
  // the wide bands below, a roughly-correct pose scores 1.0 and one sloppy
  // detail still passes. Raise toward 0.95+ for an older/steadier group.
  confidenceThreshold: 0.85,
  confidenceOverrides: { D: 0.80 }, // per-pose threshold overrides
  holdSeconds: 5.0,               // everyone must hold the pose this long
  // One alphabet per round; the next round unlocks when the mission completes.
  roundAlphabets: ["ABCD", "EFGH", "ABCDEFGH"],
  // Mystery rounds (by index): code hidden; participants follow their skeleton
  // and must hold their found pose for holdSeconds (individual countdowns).
  mysteryRounds: [2],

  // --- Flow timing ---
  lineupStableSeconds: 1.5,       // n people must be seen this long before start
  detectedMessageSeconds: 3.0,    // "Detected n adventurers..." display time
  // Hold time only ever accumulates while the pose is actually green. This
  // grace lets a break shorter than the given time PAUSE the clock instead of
  // clearing it; red time is never credited either way. At 0 any red frame
  // resets the hold immediately, which is the clearest feedback for kids -
  // the wiggle room lives in the pose bands below, not in the timer.
  breakGraceSeconds: 0.0,
  roundAdvanceSeconds: 4.0,       // "round complete" interstitial duration
  devAdvanceSeconds: 3.0,         // dev mode: pause on "complete" before next pose

  // --- Detection ---
  frameWidth: 1280,
  frameHeight: 720,
  minPoseDetectionConfidence: 0.5,
  minPosePresenceConfidence: 0.5,
  minTrackingConfidence: 0.5,
  // A camera that is blocked, in use elsewhere, or asleep hands back frames that
  // are pure black instead of failing, so watch brightness and say so out loud.
  blackFrameThreshold: 6.0,       // mean 0-255 brightness counted as "no image"
  blackFrameSeconds: 2.5,         // how long it must stay dark before we warn
  wasmBaseUrl: "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm",
  modelUrl: "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",

  // --- Display ---
  mirrorDisplay: true,            // selfie view so participants can self-correct

  // --- Pose geometry tolerances (angles in degrees; distances normalized by
  // torso length unless noted). Mirrors PoseTuning in the Python app.
  // Bands are tuned for kids: the "ideal" range that scores a full 1.0 is
  // generous, and the zero points are far out so being off gives partial
  // credit instead of a hard fail.
  // Poses are also tuned to be COMPACT: the camera has to fit up to
  // maxParticipants kids side by side, so no pose asks for a limb stretched
  // out sideways. Every pose fits in roughly 1.3 torso-lengths of width (a kid
  // standing still is already 0.75). Widening a band below costs floor space. ---
  tuning: {
    minVisibility: 0.4,

    // Pose A: crane guard (fists up by the chin, elbows in, left knee raised)
    aFistToFaceMax: 0.70,
    aFistToFaceZero: 1.15,
    aElbowBelowWristMin: 0.30,
    aElbowBelowWristZero: -0.05,
    aElbowTuckTol: 0.32,
    aElbowTuckZero: 0.80,
    // Saturates at a modest lift with a wide ramp below it, so a raised foot
    // that sinks a little stays green instead of flickering.
    aLegRaiseMin: 0.10,
    aLegRaiseZero: -0.02, // but level feet must NOT earn much credit
    aKneeBendIdealHi: 145.0,
    aKneeBendZero: 172.0,

    // Pose B: tilted X. The lower edge of the left-arm band stays meaningful:
    // a near-vertical left arm is the tree pose (F), not the tilted X. The
    // upper edge keeps the pose narrow - past ~40 degrees it is a wingspan.
    bLeftArmDiagLo: 17.0,
    bLeftArmDiagHi: 38.0,
    bLeftArmDiagZeroLo: 5.0,
    bLeftArmDiagZeroHi: 62.0,
    bRightArmVertHi: 22.0,
    bRightArmVertZero: 52.0,
    bElbowStraightMin: 135.0,
    bElbowStraightZero: 90.0,
    // The arms make an X, so the hands are far apart. Without this the pose is
    // under-specified: the tree (F) satisfies everything else and scores 0.80.
    bWristsApartMin: 0.55,
    bWristsApartZero: 0.20,
    bLegRaiseMin: 0.10,
    bLegRaiseZero: -0.02,

    // Pose C: squat with arms forward
    cKneeBendIdealHi: 145.0,
    cKneeBendZero: 178.0,
    cHipDropIdealHi: 0.62,
    cHipDropZero: 1.15,
    cWristHeightTol: 0.45,
    cWristHeightZero: 0.95,
    cElbowExtendedMin: 100.0,
    cElbowExtendedZero: 60.0,

    // Pose D: frog crouch (all the way down, knees out, hands to the floor).
    // The old goalpost arms were replaced: upper arms held out to the side are
    // the widest thing a body can do.
    dKneeBendIdealHi: 100.0,
    dKneeBendZero: 165.0,
    dHipDropIdealHi: 0.35,
    dHipDropZero: 0.85,
    dHandsBelowKneeMin: 0.15,
    dHandsBelowKneeZero: -0.25,
    dKneesOutMin: 0.15,
    dKneesOutZero: -0.20,

    // Pose E: rocket (one arm straight up, the other pressed down, feet together)
    eUpArmAngleMax: 25.0,
    eUpArmAngleZero: 55.0,
    eUpWristAboveHeadMin: 0.25,
    eUpWristAboveHeadZero: -0.10,
    eElbowStraightMin: 140.0,
    eElbowStraightZero: 95.0,
    eDownArmAngleMin: 162.0,
    eDownArmAngleZero: 125.0,
    // Distance to the hip, not just horizontal offset: an arm raised straight up
    // is also close to the hip in x, and would otherwise count as "pinned down".
    eDownWristToHipMax: 0.55,
    eDownWristToHipZero: 1.20,
    eFeetTogetherMax: 0.30,
    eFeetTogetherZero: 1.00,
    eLegStraightMin: 150.0,
    eLegStraightZero: 105.0,

    // Pose F: tree
    fFootToKneeMax: 0.45,
    fFootToKneeZero: 0.85,
    fArmAngleMax: 40.0,
    fArmAngleZero: 70.0,
    fElbowStraightMin: 135.0,
    fElbowStraightZero: 90.0,
    fHandsTogetherMax: 0.40,
    fHandsTogetherZero: 1.05,

    // Pose G: archer aiming at the sky (bow arm up on a diagonal rather than
    // out to the side: same shape, a third of the floor space). Stance is
    // normalized by torso length, robust to turning.
    gBowArmIdealLo: 15.0,
    gBowArmIdealHi: 42.0,
    gBowArmZeroLo: 2.0,
    gBowArmZeroHi: 75.0,
    gStraightElbowMin: 135.0,
    gStraightElbowZero: 90.0,
    gBowWristFromFaceMin: 0.80,
    gBowWristFromFaceZero: 0.30,
    gBentElbowLo: 25.0,
    gBentElbowHi: 125.0,
    gBentElbowZeroLo: 5.0,
    gBentElbowZeroHi: 155.0,
    gWristToChinMax: 0.50,
    gWristToChinZero: 1.10,
    gStanceWidthMin: 0.35,
    gStanceWidthZero: 0.0,

    // Pose H: knee hug
    hKneeLiftMin: 0.06,
    hKneeLiftZero: -0.12,
    hKneeBendMax: 110.0,
    hKneeBendZero: 155.0,
    hWristToKneeMax: 0.50,
    hWristToKneeZero: 0.90,
    hStandLegStraightMin: 135.0,
    hStandLegStraightZero: 90.0,
  },
};
