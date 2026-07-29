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

    Poses are also tuned to be COMPACT. The camera has to fit up to
    max_participants kids side by side, so no pose asks for a limb stretched
    out sideways: arms go up or stay tucked, stances stay near shoulder width.
    Every pose fits in roughly 1.3 torso-lengths of width (a kid standing
    still is already 0.75). Widening any band below costs floor space.
    """

    # Minimum average landmark visibility required before a pose can score at all.
    min_visibility: float = 0.4

    # --- Pose A: crane guard (fists up by the chin, elbows in, left knee raised) ---
    a_fist_to_face_max: float = 0.70     # wrist near the chin (fraction of torso)
    a_fist_to_face_zero: float = 1.15
    a_elbow_below_wrist_min: float = 0.30  # elbow carried under the fist (fraction of torso)
    a_elbow_below_wrist_zero: float = -0.05
    a_elbow_tuck_tol: float = 0.32       # |elbow.x - shoulder.x| / torso; elbows stay in
    a_elbow_tuck_zero: float = 0.80
    # Saturates at a modest lift with a wide ramp below it, so a raised foot
    # that sinks a little stays green instead of flickering.
    a_leg_raise_min: float = 0.10        # left ankle above right ankle (fraction of torso)
    a_leg_raise_zero: float = -0.02      # but level feet must NOT earn much credit
    a_knee_bend_ideal_hi: float = 145.0  # left knee angle at or below this = bent enough
    a_knee_bend_zero: float = 172.0

    # --- Pose B: tilted X (left arm diagonal, right arm straight up, right leg raised) ---
    # The lower edge stays meaningful: a near-vertical left arm is the tree
    # pose (F), not the tilted X, so it must not score as "diagonal". The upper
    # edge is what keeps the pose narrow - an arm out past ~45 degrees is a
    # wingspan, not a tilt.
    b_left_arm_diag_lo: float = 17.0     # left arm angle from vertical, ideal band
    b_left_arm_diag_hi: float = 38.0
    b_left_arm_diag_zero_lo: float = 5.0
    b_left_arm_diag_zero_hi: float = 62.0
    b_right_arm_vert_hi: float = 22.0    # right arm within this angle of vertical
    b_right_arm_vert_zero: float = 52.0
    b_elbow_straight_min: float = 135.0
    b_elbow_straight_zero: float = 90.0
    # The arms make an X, so the hands are far apart. Without this the pose is
    # under-specified: the tree (F) satisfies everything else and scores 0.80.
    b_wrists_apart_min: float = 0.55     # wrist-to-wrist distance (fraction of torso)
    b_wrists_apart_zero: float = 0.20
    b_leg_raise_min: float = 0.10        # right ankle above left ankle (fraction of torso)
    b_leg_raise_zero: float = -0.02

    # --- Pose C: squat with arms forward ---
    c_knee_bend_ideal_hi: float = 145.0  # knee angle at or below this = fully bent enough
    c_knee_bend_zero: float = 178.0
    c_hip_drop_ideal_hi: float = 0.62    # (knee.y - hip.y) / torso; small = deep squat
    c_hip_drop_zero: float = 1.15
    c_wrist_height_tol: float = 0.45     # |wrist.y - shoulder.y| / torso
    c_wrist_height_zero: float = 0.95
    c_elbow_extended_min: float = 100.0  # arms reaching forward, not tucked
    c_elbow_extended_zero: float = 60.0

    # --- Pose E: rocket (one arm straight up, the other pressed down at the
    # side, feet together). Either arm may be the raised one. ---
    e_up_arm_angle_max: float = 25.0      # raised arm within this angle of vertical
    e_up_arm_angle_zero: float = 55.0
    e_up_wrist_above_head_min: float = 0.25  # wrist above the nose (fraction of torso)
    e_up_wrist_above_head_zero: float = -0.10
    e_elbow_straight_min: float = 140.0
    e_elbow_straight_zero: float = 95.0
    e_down_arm_angle_min: float = 162.0   # pressed arm points down (180 = straight down)
    e_down_arm_angle_zero: float = 125.0
    # Distance to the hip, not just horizontal offset: an arm raised straight up
    # is also close to the hip in x, and would otherwise count as "pinned down".
    e_down_wrist_to_hip_max: float = 0.55  # wrist near the hip (fraction of torso)
    e_down_wrist_to_hip_zero: float = 1.20
    e_feet_together_max: float = 0.30     # ankle spread (fraction of torso)
    e_feet_together_zero: float = 1.00
    e_leg_straight_min: float = 150.0     # standing tall, both knees straight
    e_leg_straight_zero: float = 105.0

    # --- Pose F: tree (foot on other knee, arms overhead with hands together) ---
    f_foot_to_knee_max: float = 0.45      # raised ankle near other knee (fraction of torso)
    f_foot_to_knee_zero: float = 0.85
    f_arm_angle_max: float = 40.0         # arms within this angle of vertical
    f_arm_angle_zero: float = 70.0
    f_elbow_straight_min: float = 135.0
    f_elbow_straight_zero: float = 90.0
    f_hands_together_max: float = 0.40    # wrist-to-wrist distance (fraction of torso)
    f_hands_together_zero: float = 1.05

    # --- Pose G: archer aiming at the sky (bow arm up on a diagonal, other
    # elbow bent pulling to the chin, feet a little apart) ---
    # The bow arm points up rather than out to the side: same shape, a third
    # of the floor space.
    g_bow_arm_ideal_lo: float = 15.0       # bow arm angle from vertical
    g_bow_arm_ideal_hi: float = 42.0
    g_bow_arm_zero_lo: float = 2.0
    g_bow_arm_zero_hi: float = 75.0
    g_straight_elbow_min: float = 135.0
    g_straight_elbow_zero: float = 90.0
    g_bow_wrist_from_face_min: float = 0.80  # bow hand reaches away from the face
    g_bow_wrist_from_face_zero: float = 0.30
    g_bent_elbow_lo: float = 25.0          # drawing-arm elbow angle band
    g_bent_elbow_hi: float = 125.0
    g_bent_elbow_zero_lo: float = 5.0
    g_bent_elbow_zero_hi: float = 155.0
    g_wrist_to_chin_max: float = 0.50      # bent-arm wrist near the chin (fraction of torso)
    g_wrist_to_chin_zero: float = 1.10
    # Ankle spread normalized by torso length, NOT shoulder width: shoulders
    # collapse in x when the archer turns sideways, torso length doesn't.
    g_stance_width_min: float = 0.35
    g_stance_width_zero: float = 0.0

    # --- Pose H: knee hug (knee pulled to chest with both hands) ---
    h_knee_lift_min: float = 0.06          # raised knee above hip (fraction of torso)
    h_knee_lift_zero: float = -0.12
    h_knee_bend_max: float = 110.0         # raised knee tightly bent
    h_knee_bend_zero: float = 155.0
    h_wrist_to_knee_max: float = 0.50      # each wrist near the raised knee
    h_wrist_to_knee_zero: float = 0.90
    h_stand_leg_straight_min: float = 135.0
    h_stand_leg_straight_zero: float = 90.0

    # --- Pose D: frog crouch (all the way down, knees pushed out, hands to the
    # floor between the feet). The old goalpost arms were replaced: upper arms
    # held out to the side are the widest thing a body can do, and pointing
    # them at the camera instead makes the elbow angle unmeasurable in 2D. ---
    d_knee_bend_ideal_hi: float = 100.0  # knee angle at or below this = deep enough
    d_knee_bend_zero: float = 165.0
    d_hip_drop_ideal_hi: float = 0.35    # (knee.y - hip.y) / torso; hips down at knee level
    d_hip_drop_zero: float = 0.85
    d_hands_below_knee_min: float = 0.15  # wrist below the knee (fraction of torso)
    d_hands_below_knee_zero: float = -0.25
    d_knees_out_min: float = 0.15        # knee spread beyond ankle spread (fraction of torso)
    d_knees_out_zero: float = -0.20


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
    # Hold time only ever accumulates while the pose is actually green. This
    # grace lets a break shorter than the given time PAUSE the clock instead of
    # clearing it; red time is never credited either way. At 0 any red frame
    # resets the hold immediately, which is the clearest feedback for kids -
    # the wiggle room lives in the pose bands below, not in the timer.
    break_grace_seconds: float = 0.0
    round_advance_seconds: float = 4.0     # "round complete" interstitial before the next round
    dev_advance_seconds: float = 3.0       # dev mode: pause on "complete" before next pose

    # --- Detection ---
    camera_index: int = 0
    frame_width: int = 1280
    frame_height: int = 720
    min_pose_detection_confidence: float = 0.5
    min_pose_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    # A camera that is blocked, in use elsewhere, or denied at the OS level hands
    # back pure black frames instead of failing, so watch brightness and say so.
    black_frame_threshold: float = 6.0   # mean 0-255 brightness counted as "no image"
    black_frame_seconds: float = 2.5     # how long it must stay dark before we warn
    model_path: str = "models/pose_landmarker_full.task"
    model_url: str = (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
    )

    # --- Display ---
    mirror_display: bool = True   # selfie view so participants can self-correct
    window_name: str = "Master your skills"

    tuning: PoseTuning = field(default_factory=PoseTuning)
