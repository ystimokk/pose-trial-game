"""Central configuration for the Master your skills station.

Every numeric value used by the app lives here so each build can be tuned
without touching the logic. Only `n` (the number of participants) is dynamic
and is provided by the admin at launch.
"""

from dataclasses import dataclass, field


@dataclass
class PoseTuning:
    """Geometry tolerances used by the pose scorers (all angles in degrees,
    all distances normalized by torso length unless noted).

    Bands are tuned for kids: the "ideal" range that scores a full 1.0 is
    generous, so a roughly-right pose counts, and the zero points are far out
    so being off gives partial credit instead of a hard fail.
    """

    # Minimum average landmark visibility required before a pose can score at all.
    min_visibility: float = 0.4

    # --- Pose A: crane stance (arms up in a Y, left knee raised and bent) ---
    a_arm_angle_ideal_lo: float = 5.0    # arm angle from vertical, ideal band
    a_arm_angle_ideal_hi: float = 60.0
    a_arm_angle_zero: float = 90.0       # score reaches 0 at this angle
    a_elbow_straight_min: float = 135.0  # elbow angle for a "straight" arm
    a_elbow_straight_zero: float = 90.0
    a_leg_raise_min: float = 0.07        # left ankle above right ankle (fraction of torso)
    a_leg_raise_zero: float = 0.0
    a_knee_bend_ideal_hi: float = 145.0  # left knee angle at or below this = bent enough
    a_knee_bend_zero: float = 172.0

    # --- Pose B: tilted X (left arm diagonal, right arm straight up, right leg raised) ---
    # The lower edge stays meaningful: a near-vertical left arm is the tree
    # pose (F), not the tilted X, so it must not score as "diagonal".
    b_left_arm_diag_lo: float = 22.0     # left arm angle from vertical, ideal band
    b_left_arm_diag_hi: float = 75.0
    b_left_arm_diag_zero_lo: float = 10.0
    b_left_arm_diag_zero_hi: float = 100.0
    b_right_arm_vert_hi: float = 35.0    # right arm within this angle of vertical
    b_right_arm_vert_zero: float = 65.0
    b_elbow_straight_min: float = 135.0
    b_elbow_straight_zero: float = 90.0
    b_leg_raise_min: float = 0.035       # right ankle above left ankle (fraction of torso)
    b_leg_raise_ideal: float = 0.15
    b_leg_raise_zero: float = 0.0

    # --- Pose C: squat with arms forward ---
    c_knee_bend_ideal_hi: float = 145.0  # knee angle at or below this = fully bent enough
    c_knee_bend_zero: float = 178.0
    c_hip_drop_ideal_hi: float = 0.62    # (knee.y - hip.y) / torso; small = deep squat
    c_hip_drop_zero: float = 0.95
    c_wrist_height_tol: float = 0.45     # |wrist.y - shoulder.y| / torso
    c_wrist_height_zero: float = 0.85
    c_elbow_extended_min: float = 100.0  # arms reaching forward, not tucked
    c_elbow_extended_zero: float = 60.0

    # --- Pose E: airplane (one-leg balance, torso tilted forward, leg back;
    # arms are NOT scored - they stay along the body like a figure skater) ---
    e_torso_tilt_ideal_lo: float = 35.0   # torso angle from vertical, ideal band
    e_torso_tilt_ideal_hi: float = 110.0
    e_torso_tilt_zero_lo: float = 15.0
    e_torso_tilt_zero_hi: float = 140.0
    e_leg_raise_min: float = 0.22         # back ankle above standing ankle (fraction of torso)
    e_leg_raise_zero: float = 0.02
    e_knee_straight_min: float = 135.0    # raised leg roughly straight
    e_knee_straight_zero: float = 90.0

    # --- Pose F: tree (foot on other knee, arms overhead with hands together) ---
    f_foot_to_knee_max: float = 0.45      # raised ankle near other knee (fraction of torso)
    f_foot_to_knee_zero: float = 0.85
    f_arm_angle_max: float = 40.0         # arms within this angle of vertical
    f_arm_angle_zero: float = 70.0
    f_elbow_straight_min: float = 135.0
    f_elbow_straight_zero: float = 90.0
    f_hands_together_max: float = 0.40    # wrist-to-wrist distance (fraction of torso)
    f_hands_together_zero: float = 0.75

    # --- Pose G: archer (one arm straight out, other bent to chin, wide stance) ---
    g_straight_arm_ideal_lo: float = 60.0  # arm angle from vertical (90 = horizontal)
    g_straight_arm_ideal_hi: float = 120.0
    g_straight_arm_zero_lo: float = 35.0
    g_straight_arm_zero_hi: float = 150.0
    g_straight_elbow_min: float = 135.0
    g_straight_elbow_zero: float = 90.0
    g_bent_elbow_lo: float = 25.0          # drawing-arm elbow angle band
    g_bent_elbow_hi: float = 125.0
    g_bent_elbow_zero_lo: float = 5.0
    g_bent_elbow_zero_hi: float = 155.0
    g_wrist_to_chin_max: float = 0.50      # bent-arm wrist near the chin (fraction of torso)
    g_wrist_to_chin_zero: float = 0.85
    # Ankle spread normalized by torso length, NOT shoulder width: shoulders
    # collapse in x when the archer turns sideways, torso length doesn't.
    g_stance_width_min: float = 0.7
    g_stance_width_zero: float = 0.35

    # --- Pose H: knee hug (knee pulled to chest with both hands) ---
    h_knee_lift_min: float = 0.06          # raised knee above hip (fraction of torso)
    h_knee_lift_zero: float = -0.12
    h_knee_bend_max: float = 110.0         # raised knee tightly bent
    h_knee_bend_zero: float = 155.0
    h_wrist_to_knee_max: float = 0.50      # each wrist near the raised knee
    h_wrist_to_knee_zero: float = 0.90
    h_stand_leg_straight_min: float = 135.0
    h_stand_leg_straight_zero: float = 90.0

    # --- Pose D: frog (goalpost arms folded upward, wide bent legs) ---
    d_elbow_bend_lo: float = 40.0        # elbow angle ideal band (folded ~90 degrees)
    d_elbow_bend_hi: float = 135.0
    d_elbow_bend_zero_lo: float = 15.0
    d_elbow_bend_zero_hi: float = 165.0
    d_wrist_above_elbow_min: float = 0.02  # wrist above elbow (fraction of torso)
    d_elbow_height_tol: float = 0.45     # |elbow.y - shoulder.y| / torso
    d_elbow_height_zero: float = 0.80
    d_stance_width_min: float = 1.15     # ankle spread / shoulder width
    d_stance_width_ideal: float = 1.8
    d_stance_width_zero: float = 0.8
    d_knee_bend_ideal_hi: float = 163.0  # knee angle at or below this = bent enough
    d_knee_bend_zero: float = 178.0


@dataclass
class AppConfig:
    """Top-level app parameters. Tweak per build."""

    # --- Gameplay ---
    max_participants: int = 5          # upper bound for n
    # Pose counts only above this score. Kept forgiving for kids: combined with
    # the wide bands above, a roughly-correct pose scores 1.0 and one sloppy
    # detail still passes. Raise toward 0.95+ for an older/steadier group.
    confidence_threshold: float = 0.85
    # Per-pose overrides for poses that are harder to score cleanly.
    confidence_overrides: dict = field(default_factory=lambda: {"D": 0.80})
    hold_seconds: float = 5.0          # everyone must hold the pose this long
    # One alphabet per round; the next round unlocks when the mission completes.
    round_alphabets: tuple = ("ABCD", "EFGH", "ABCDEFGH")
    # Mystery rounds (by index): the code is hidden. Participants see their
    # skeleton with per-limb feedback and solve their pose by trial and error.
    # Each person must hold their found pose for hold_seconds (individual
    # countdowns); once held, they are locked in.
    mystery_rounds: tuple = (2,)

    # --- Flow timing ---
    lineup_stable_seconds: float = 1.5     # n people must be seen this long before start
    detected_message_seconds: float = 3.0  # "Detected n adventurers..." display time
    break_grace_seconds: float = 0.4       # forgive a wobble shorter than this
    round_advance_seconds: float = 4.0     # "round complete" interstitial before the next round
    dev_advance_seconds: float = 3.0       # dev mode: pause on "complete" before next pose

    # --- Detection ---
    camera_index: int = 0
    frame_width: int = 1280
    frame_height: int = 720
    min_pose_detection_confidence: float = 0.5
    min_pose_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    model_path: str = "models/pose_landmarker_full.task"
    model_url: str = (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
    )

    # --- Display ---
    mirror_display: bool = True   # selfie view so participants can self-correct
    window_name: str = "Master your skills"

    tuning: PoseTuning = field(default_factory=PoseTuning)
