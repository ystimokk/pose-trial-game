"""Pose scorers for the trial poses.

Each scorer takes the 33 MediaPipe pose landmarks for one person and returns a
PoseResult: a total confidence in [0, 1] plus a per-body-part breakdown used by
hint mode to show WHICH limb is right or wrong. The total is the mean of all
sub-criteria, each shaped by a trapezoid function: 1.0 inside the ideal band,
falling linearly to 0.0 at the hard limits. Holding the pose correctly
therefore yields 1.0, which clears the (parameterized) 95% threshold.

Landmark coordinates are MediaPipe-normalized: x, y in [0, 1] with y pointing
down. Distances are normalized by torso length so scores are size-invariant.
"""

import math
from dataclasses import dataclass, field
from types import SimpleNamespace

from .config import PoseTuning

# MediaPipe pose landmark indices
NOSE = 0
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28

# Body-part names used in per-part feedback
L_ARM, R_ARM, L_LEG, R_LEG, TORSO = "left_arm", "right_arm", "left_leg", "right_leg", "torso"

POSE_DESCRIPTIONS = {
    "A": "Crane stance: arms high in a Y, left knee raised and bent",
    "B": "Tilted X: left arm diagonal, right arm straight up, right leg raised",
    "C": "Squat down with both arms reaching forward",
    "D": "Frog: arms folded pointing to the sky, legs wide and bent",
    "E": "Airplane: balance on one leg, torso tilted forward, other leg back, arms along the body",
    "F": "Tree: one foot on the other knee, arms overhead with hands together",
    "G": "Archer: one arm straight out, other elbow bent pulling to the chin, wide stance",
    "H": "Knee hug: pull one knee to your chest with both hands",
}


@dataclass
class PoseResult:
    total: float
    parts: dict = field(default_factory=dict)  # part name -> score in [0, 1]


class _Criteria:
    """Collects (body part, score) pairs and aggregates them."""

    def __init__(self):
        self._items = []

    def add(self, part: str, score: float):
        self._items.append((part, score))

    def total(self) -> float:
        return sum(s for _, s in self._items) / len(self._items)

    def result(self) -> PoseResult:
        by_part = {}
        for part, score in self._items:
            by_part.setdefault(part, []).append(score)
        parts = {p: sum(v) / len(v) for p, v in by_part.items()}
        return PoseResult(self.total(), parts)


def _trapezoid(value: float, zero_lo: float, one_lo: float, one_hi: float, zero_hi: float) -> float:
    """1.0 inside [one_lo, one_hi], linearly 0 at zero_lo / zero_hi."""
    if value <= zero_lo or value >= zero_hi:
        return 0.0
    if one_lo <= value <= one_hi:
        return 1.0
    if value < one_lo:
        return (value - zero_lo) / (one_lo - zero_lo)
    return (zero_hi - value) / (zero_hi - one_hi)


def _at_least(value: float, zero: float, one: float) -> float:
    """Ramps from 0 at `zero` to 1 at `one` (works for either direction)."""
    if zero == one:
        return 1.0 if value >= one else 0.0
    t = (value - zero) / (one - zero)
    return max(0.0, min(1.0, t))


def _at_most(value: float, one: float, zero: float) -> float:
    """1.0 at or below `one`, ramping to 0 at `zero`."""
    return _at_least(-value, -zero, -one)


def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _midpoint(a, b):
    return SimpleNamespace(x=(a.x + b.x) / 2, y=(a.y + b.y) / 2)


def _angle_deg(a, b, c) -> float:
    """Interior angle at point b, in degrees."""
    v1 = (a.x - b.x, a.y - b.y)
    v2 = (c.x - b.x, c.y - b.y)
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 < 1e-6 or n2 < 1e-6:
        return 0.0
    cos = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cos))


def _angle_from_vertical_up(origin, tip) -> float:
    """Angle of the origin->tip vector measured from straight up, in degrees."""
    dx = tip.x - origin.x
    dy = tip.y - origin.y  # y points down
    n = math.hypot(dx, dy)
    if n < 1e-6:
        return 180.0
    cos = max(-1.0, min(1.0, -dy / n))  # up is (0, -1)
    return math.degrees(math.acos(cos))


def _torso_length(lm) -> float:
    sx = (lm[L_SHOULDER].x + lm[R_SHOULDER].x) / 2
    sy = (lm[L_SHOULDER].y + lm[R_SHOULDER].y) / 2
    hx = (lm[L_HIP].x + lm[R_HIP].x) / 2
    hy = (lm[L_HIP].y + lm[R_HIP].y) / 2
    return max(1e-6, math.hypot(sx - hx, sy - hy))


def _visibility_ok(lm, indices, tuning: PoseTuning) -> bool:
    vis = [getattr(lm[i], "visibility", 1.0) for i in indices]
    return (sum(vis) / len(vis)) >= tuning.min_visibility


ARMS = ((L_ARM, L_SHOULDER, L_ELBOW, L_WRIST), (R_ARM, R_SHOULDER, R_ELBOW, R_WRIST))
LEGS = ((L_LEG, L_HIP, L_KNEE, L_ANKLE), (R_LEG, R_HIP, R_KNEE, R_ANKLE))


def score_pose_a(lm, t: PoseTuning) -> PoseResult:
    """Crane stance: both arms straight up-and-out in a Y, left knee raised and bent."""
    needed = [L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST,
              L_HIP, L_KNEE, L_ANKLE, R_ANKLE]
    if not _visibility_ok(lm, needed, t):
        return PoseResult(0.0)

    c = _Criteria()
    for part, sh, el, wr in ARMS:
        arm_angle = _angle_from_vertical_up(lm[sh], lm[wr])
        c.add(part, _trapezoid(arm_angle, -1.0, t.a_arm_angle_ideal_lo,
                               t.a_arm_angle_ideal_hi, t.a_arm_angle_zero))
        elbow = _angle_deg(lm[sh], lm[el], lm[wr])
        c.add(part, _at_least(elbow, t.a_elbow_straight_zero, t.a_elbow_straight_min))

    torso = _torso_length(lm)
    leg_raise = (lm[R_ANKLE].y - lm[L_ANKLE].y) / torso  # positive = left ankle higher
    c.add(L_LEG, _at_least(leg_raise, t.a_leg_raise_zero, t.a_leg_raise_min))

    knee_angle = _angle_deg(lm[L_HIP], lm[L_KNEE], lm[L_ANKLE])
    c.add(L_LEG, _trapezoid(knee_angle, -1.0, 0.0, t.a_knee_bend_ideal_hi, t.a_knee_bend_zero))

    return c.result()


def score_pose_b(lm, t: PoseTuning) -> PoseResult:
    """Tilted X: left arm diagonal, right arm straight up, right leg slightly raised."""
    needed = [L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST, L_ANKLE, R_ANKLE]
    if not _visibility_ok(lm, needed, t):
        return PoseResult(0.0)

    c = _Criteria()

    left_arm = _angle_from_vertical_up(lm[L_SHOULDER], lm[L_WRIST])
    c.add(L_ARM, _trapezoid(left_arm, t.b_left_arm_diag_zero_lo, t.b_left_arm_diag_lo,
                            t.b_left_arm_diag_hi, t.b_left_arm_diag_zero_hi))

    right_arm = _angle_from_vertical_up(lm[R_SHOULDER], lm[R_WRIST])
    c.add(R_ARM, _trapezoid(right_arm, -1.0, 0.0, t.b_right_arm_vert_hi, t.b_right_arm_vert_zero))

    for part, sh, el, wr in ARMS:
        elbow = _angle_deg(lm[sh], lm[el], lm[wr])
        c.add(part, _at_least(elbow, t.b_elbow_straight_zero, t.b_elbow_straight_min))

    torso = _torso_length(lm)
    leg_raise = (lm[L_ANKLE].y - lm[R_ANKLE].y) / torso  # positive = right ankle higher
    c.add(R_LEG, _at_least(leg_raise, t.b_leg_raise_zero, t.b_leg_raise_min))

    return c.result()


def score_pose_c(lm, t: PoseTuning) -> PoseResult:
    """Squat with both arms reaching forward at shoulder height."""
    needed = [L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST,
              L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE]
    if not _visibility_ok(lm, needed, t):
        return PoseResult(0.0)

    torso = _torso_length(lm)
    c = _Criteria()

    for part, hip, knee, ankle in LEGS:
        knee_angle = _angle_deg(lm[hip], lm[knee], lm[ankle])
        c.add(part, _trapezoid(knee_angle, -1.0, 0.0, t.c_knee_bend_ideal_hi, t.c_knee_bend_zero))

    hip_y = (lm[L_HIP].y + lm[R_HIP].y) / 2
    knee_y = (lm[L_KNEE].y + lm[R_KNEE].y) / 2
    hip_drop = (knee_y - hip_y) / torso  # small when hips are low
    c.add(TORSO, _trapezoid(hip_drop, -1.0, -0.5, t.c_hip_drop_ideal_hi, t.c_hip_drop_zero))

    for part, sh, el, wr in ARMS:
        wrist_height = abs(lm[wr].y - lm[sh].y) / torso
        c.add(part, _trapezoid(wrist_height, -1.0, 0.0, t.c_wrist_height_tol, t.c_wrist_height_zero))
        elbow = _angle_deg(lm[sh], lm[el], lm[wr])
        c.add(part, _at_least(elbow, t.c_elbow_extended_zero, t.c_elbow_extended_min))

    return c.result()


def score_pose_d(lm, t: PoseTuning) -> PoseResult:
    """Frog: goalpost arms (elbows ~90 deg, hands up), legs wide and bent."""
    needed = [L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST,
              L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE]
    if not _visibility_ok(lm, needed, t):
        return PoseResult(0.0)

    torso = _torso_length(lm)
    c = _Criteria()

    for part, sh, el, wr in ARMS:
        elbow = _angle_deg(lm[sh], lm[el], lm[wr])
        c.add(part, _trapezoid(elbow, t.d_elbow_bend_zero_lo, t.d_elbow_bend_lo,
                               t.d_elbow_bend_hi, t.d_elbow_bend_zero_hi))
        wrist_up = (lm[el].y - lm[wr].y) / torso  # positive = wrist above elbow
        c.add(part, _at_least(wrist_up, 0.0, t.d_wrist_above_elbow_min))
        elbow_height = abs(lm[el].y - lm[sh].y) / torso
        c.add(part, _trapezoid(elbow_height, -1.0, 0.0, t.d_elbow_height_tol, t.d_elbow_height_zero))

    shoulder_w = max(1e-6, abs(lm[L_SHOULDER].x - lm[R_SHOULDER].x))
    ankle_w = abs(lm[L_ANKLE].x - lm[R_ANKLE].x)
    stance = ankle_w / shoulder_w
    stance_score = _trapezoid(stance, t.d_stance_width_zero, t.d_stance_width_min,
                              t.d_stance_width_ideal * 3, t.d_stance_width_ideal * 4)

    for part, hip, knee, ankle in LEGS:
        c.add(part, stance_score)
        knee_angle = _angle_deg(lm[hip], lm[knee], lm[ankle])
        c.add(part, _trapezoid(knee_angle, -1.0, 0.0, t.d_knee_bend_ideal_hi, t.d_knee_bend_zero))

    return c.result()


def score_pose_e(lm, t: PoseTuning) -> PoseResult:
    """Airplane: torso tilted forward, one leg extended back. Arms are not
    scored - they stay along the body like a figure skater. Either leg may be
    the raised one; the better-matching side is scored."""
    needed = [L_SHOULDER, R_SHOULDER, L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE]
    if not _visibility_ok(lm, needed, t):
        return PoseResult(0.0)

    torso = _torso_length(lm)

    options = []
    for (part, hip, knee, ankle), standing in ((LEGS[0], R_ANKLE), (LEGS[1], L_ANKLE)):
        c = _Criteria()

        hip_mid = _midpoint(lm[L_HIP], lm[R_HIP])
        sh_mid = _midpoint(lm[L_SHOULDER], lm[R_SHOULDER])
        tilt = _angle_from_vertical_up(hip_mid, sh_mid)
        c.add(TORSO, _trapezoid(tilt, t.e_torso_tilt_zero_lo, t.e_torso_tilt_ideal_lo,
                                t.e_torso_tilt_ideal_hi, t.e_torso_tilt_zero_hi))

        raise_amt = (lm[standing].y - lm[ankle].y) / torso
        c.add(part, _at_least(raise_amt, t.e_leg_raise_zero, t.e_leg_raise_min))
        knee_angle = _angle_deg(lm[hip], lm[knee], lm[ankle])
        c.add(part, _at_least(knee_angle, t.e_knee_straight_zero, t.e_knee_straight_min))

        options.append(c)

    return max(options, key=lambda c: c.total()).result()


def score_pose_f(lm, t: PoseTuning) -> PoseResult:
    """Tree: one foot against the other knee, arms overhead, hands together."""
    needed = [L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST,
              L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE]
    if not _visibility_ok(lm, needed, t):
        return PoseResult(0.0)

    torso = _torso_length(lm)
    c = _Criteria()

    left_foot = _dist(lm[L_ANKLE], lm[R_KNEE]) / torso  # left foot on right knee
    right_foot = _dist(lm[R_ANKLE], lm[L_KNEE]) / torso  # right foot on left knee
    raised_part = L_LEG if left_foot <= right_foot else R_LEG
    c.add(raised_part, _at_most(min(left_foot, right_foot),
                                t.f_foot_to_knee_max, t.f_foot_to_knee_zero))

    for part, sh, el, wr in ARMS:
        arm_angle = _angle_from_vertical_up(lm[sh], lm[wr])
        c.add(part, _at_most(arm_angle, t.f_arm_angle_max, t.f_arm_angle_zero))
        elbow = _angle_deg(lm[sh], lm[el], lm[wr])
        c.add(part, _at_least(elbow, t.f_elbow_straight_zero, t.f_elbow_straight_min))

    hands = _at_most(_dist(lm[L_WRIST], lm[R_WRIST]) / torso,
                     t.f_hands_together_max, t.f_hands_together_zero)
    c.add(L_ARM, hands)
    c.add(R_ARM, hands)

    return c.result()


def score_pose_g(lm, t: PoseTuning) -> PoseResult:
    """Archer: one arm straight out to the side, the other elbow bent with the
    wrist drawn to the chin, feet in a wide stance. Either arm may draw."""
    needed = [NOSE, L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST,
              L_ANKLE, R_ANKLE]
    if not _visibility_ok(lm, needed, t):
        return PoseResult(0.0)

    torso = _torso_length(lm)

    stance = abs(lm[L_ANKLE].x - lm[R_ANKLE].x) / torso
    stance_score = _at_least(stance, t.g_stance_width_zero, t.g_stance_width_min)

    options = []
    for straight, bent in ((ARMS[0], ARMS[1]), (ARMS[1], ARMS[0])):
        s_part, s_sh, s_el, s_wr = straight
        b_part, b_sh, b_el, b_wr = bent
        c = _Criteria()

        arm_angle = _angle_from_vertical_up(lm[s_sh], lm[s_wr])
        c.add(s_part, _trapezoid(arm_angle, t.g_straight_arm_zero_lo, t.g_straight_arm_ideal_lo,
                                 t.g_straight_arm_ideal_hi, t.g_straight_arm_zero_hi))
        elbow = _angle_deg(lm[s_sh], lm[s_el], lm[s_wr])
        c.add(s_part, _at_least(elbow, t.g_straight_elbow_zero, t.g_straight_elbow_min))

        bent_angle = _angle_deg(lm[b_sh], lm[b_el], lm[b_wr])
        c.add(b_part, _trapezoid(bent_angle, t.g_bent_elbow_zero_lo, t.g_bent_elbow_lo,
                                 t.g_bent_elbow_hi, t.g_bent_elbow_zero_hi))
        chin = _dist(lm[b_wr], lm[NOSE]) / torso
        c.add(b_part, _at_most(chin, t.g_wrist_to_chin_max, t.g_wrist_to_chin_zero))

        c.add(L_LEG, stance_score)
        c.add(R_LEG, stance_score)

        options.append(c)

    return max(options, key=lambda c: c.total()).result()


def score_pose_h(lm, t: PoseTuning) -> PoseResult:
    """Knee hug: one knee pulled to the chest with both hands, standing tall."""
    needed = [L_WRIST, R_WRIST, L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE]
    if not _visibility_ok(lm, needed, t):
        return PoseResult(0.0)

    torso = _torso_length(lm)

    options = []
    for raised, standing in ((LEGS[0], LEGS[1]), (LEGS[1], LEGS[0])):
        part, hip, knee, ankle = raised
        o_part, o_hip, o_knee, o_ankle = standing
        c = _Criteria()

        lift = (lm[hip].y - lm[knee].y) / torso  # positive = knee above hip
        c.add(part, _at_least(lift, t.h_knee_lift_zero, t.h_knee_lift_min))
        knee_angle = _angle_deg(lm[hip], lm[knee], lm[ankle])
        c.add(part, _at_most(knee_angle, t.h_knee_bend_max, t.h_knee_bend_zero))

        for a_part, wr in ((L_ARM, L_WRIST), (R_ARM, R_WRIST)):
            hug = _dist(lm[wr], lm[knee]) / torso
            c.add(a_part, _at_most(hug, t.h_wrist_to_knee_max, t.h_wrist_to_knee_zero))

        stand_angle = _angle_deg(lm[o_hip], lm[o_knee], lm[o_ankle])
        c.add(o_part, _at_least(stand_angle, t.h_stand_leg_straight_zero,
                                t.h_stand_leg_straight_min))

        options.append(c)

    return max(options, key=lambda c: c.total()).result()


POSE_SCORERS = {
    "A": score_pose_a,
    "B": score_pose_b,
    "C": score_pose_c,
    "D": score_pose_d,
    "E": score_pose_e,
    "F": score_pose_f,
    "G": score_pose_g,
    "H": score_pose_h,
}
