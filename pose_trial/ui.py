"""On-screen UI rendering (OpenCV).

No bounding boxes, no confidence numbers: participants only see their pose
name, green when the pose is held well enough, dark red otherwise.
"""

import cv2
import numpy as np

from .poses import POSE_NAMES

GREEN = (80, 220, 80)
DARK_RED = (40, 40, 170)
WHITE = (245, 245, 245)
ACCENT = (255, 200, 80)
WARN = (77, 184, 255)
PANEL = (20, 16, 12)

FONT = cv2.FONT_HERSHEY_DUPLEX


def _blend(frame, overlay, alpha: float):
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, dst=frame)


def _text_size(text, scale, thickness):
    (w, h), _ = cv2.getTextSize(text, FONT, scale, thickness)
    return w, h


def _put_centered(img, text, cx, cy, scale, color, thickness):
    w, h = _text_size(text, scale, thickness)
    cv2.putText(img, text, (int(cx - w / 2), int(cy + h / 2)), FONT, scale,
                color, thickness, cv2.LINE_AA)


def _fit_scale(text, max_w, scale, thickness):
    """Shrink `scale` until `text` fits in `max_w`. Pose names are far wider
    than the single letters they replaced, so a five-adventurer line-up has to
    scale itself down rather than run its labels together."""
    w, _ = _text_size(text, scale, thickness)
    return scale if w <= max_w else scale * max_w / w


def draw_dim_panel(frame, y0, y1, alpha=0.55):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, y0), (frame.shape[1], y1), PANEL, -1)
    _blend(frame, overlay, alpha)


def draw_banner(frame, title, subtitle=None):
    """Large centered message with an optional subtitle."""
    h, w = frame.shape[:2]
    draw_dim_panel(frame, int(h * 0.32), int(h * 0.58))
    _put_centered(frame, title, w / 2, h * 0.42, 1.6, WHITE, 3)
    if subtitle:
        _put_centered(frame, subtitle, w / 2, h * 0.52, 0.9, ACCENT, 2)


def draw_camera_warning(frame, camera_index: int):
    """Banner shown when the camera is delivering nothing but black frames."""
    h, w = frame.shape[:2]
    lines = [
        f"Camera {camera_index} is on, but every frame is black.",
        "Check the lens cover, close other apps using the camera,",
        "or quit and run:  python main.py --list-cameras",
    ]
    draw_dim_panel(frame, int(h * 0.02), int(h * 0.20), alpha=0.75)
    _put_centered(frame, lines[0], w / 2, h * 0.07, 1.0, WARN, 2)
    for i, line in enumerate(lines[1:]):
        _put_centered(frame, line, w / 2, h * (0.12 + 0.045 * i), 0.7, WHITE, 1)


def draw_lineup(frame, detected: int, n: int):
    draw_banner(frame, "Adventurers, line up!",
                f"Waiting for {n} adventurers... ({detected} in view)")


def draw_detected(frame, n: int):
    draw_banner(frame, f"Detected {n} adventurers...", "Starting the trial.")


def draw_pose_code(frame, letters, statuses):
    """Top strip showing the pose code; each pose name green when its
    participant is holding the pose, dark red otherwise."""
    h, w = frame.shape[:2]
    strip_h = int(h * 0.17)
    draw_dim_panel(frame, 0, strip_h, alpha=0.6)

    n = len(letters)
    slot = w / (n + 1)
    names = [POSE_NAMES[c] for c in letters]
    # One scale for the whole row, set by the longest name: sizing each name
    # independently makes the strip look ragged.
    scale = min(_fit_scale(name, slot * 0.86, 2.4, 6) for name in names)
    for i, (name, ok) in enumerate(zip(names, statuses)):
        color = GREEN if ok else DARK_RED
        _put_centered(frame, name, slot * (i + 1), strip_h * 0.52, scale, color, 6)


def draw_person_names(frame, anchors):
    """Pose name floating above each participant's head.

    anchors: list of (letter, ok, x_px, y_px) in display coordinates.
    """
    w = frame.shape[1]
    max_w = w / (len(anchors) + 1) * 0.9
    scale = min(_fit_scale(POSE_NAMES[letter], max_w, 1.8, 5)
                for letter, *_ in anchors)
    for letter, ok, x, y in anchors:
        color = GREEN if ok else DARK_RED
        _put_centered(frame, POSE_NAMES[letter], x, max(40, y - 60), scale, color, 5)


def _countdown_number(remaining: float, total: float):
    """Shared fade math: which number to show and its fade-in/out alpha."""
    number = int(np.ceil(remaining))
    number = max(1, min(int(total), number))
    progress = 1.0 - (remaining - (number - 1))  # 0 -> 1 within this number's second
    if progress < 0.15:
        alpha = progress / 0.15
    elif progress > 0.65:
        alpha = max(0.0, (1.0 - progress) / 0.35)
    else:
        alpha = 1.0
    return number, alpha


def _put_fading_number(frame, number: int, alpha: float, cx, cy, scale, color, thickness):
    overlay = frame.copy()
    _put_centered(overlay, str(number), cx, cy, scale, color, thickness)
    _blend(frame, overlay, alpha)


def draw_status_circles(frame, states, total_seconds: float):
    """Mystery round top strip, one marker per participant:
    green circle = pose solved and locked in; fading countdown number =
    currently holding their pose; red circle = still searching.

    states: list of (solved, remaining_hold) with remaining_hold None unless
    the person is mid-hold."""
    h, w = frame.shape[:2]
    strip_h = int(h * 0.17)
    draw_dim_panel(frame, 0, strip_h, alpha=0.6)

    n = len(states)
    slot = w / (n + 1)
    radius = int(strip_h * 0.30)
    for i, (solved, remaining) in enumerate(states):
        cx, cy = int(slot * (i + 1)), int(strip_h * 0.5)
        if solved:
            cv2.circle(frame, (cx, cy), radius, GREEN, -1, cv2.LINE_AA)
        elif remaining is not None:
            number, alpha = _countdown_number(remaining, total_seconds)
            _put_fading_number(frame, number, alpha, cx, cy, 2.2, GREEN, 6)
        else:
            cv2.circle(frame, (cx, cy), radius, DARK_RED, -1, cv2.LINE_AA)


def draw_person_circles(frame, markers, total_seconds: float):
    """Mystery round marker above each head: same solved/counting/searching
    treatment as the top strip.

    markers: list of (x_px, y_px, solved, remaining_hold)."""
    for x, y, solved, remaining in markers:
        cx, cy = int(x), int(max(40, y - 70))
        if solved:
            cv2.circle(frame, (cx, cy), 22, GREEN, -1, cv2.LINE_AA)
        elif remaining is not None:
            number, alpha = _countdown_number(remaining, total_seconds)
            _put_fading_number(frame, number, alpha, cx, cy, 1.6, GREEN, 4)
        else:
            cv2.circle(frame, (cx, cy), 22, DARK_RED, -1, cv2.LINE_AA)


def draw_countdown(frame, remaining: float, total: float):
    """Modern fading countdown: each number fades in, holds, fades out."""
    h, w = frame.shape[:2]
    number, alpha = _countdown_number(remaining, total)
    progress = 1.0 - (remaining - (number - 1))

    scale = 6.0 + 1.5 * progress  # gently grows as it fades
    _put_fading_number(frame, number, alpha * 0.9, w / 2, h / 2, scale, WHITE, 10)

    _put_centered(frame, "HOLD THE POSE", w / 2, h * 0.82, 1.0, ACCENT, 2)


# Stick-figure diagrams for the info overlay. Each figure is a head circle
# plus line segments in a unit box (x right, y down).
POSE_FIGURES = {
    "A": {
        "head": (0.5, 0.20),
        "lines": [
            ((0.5, 0.28), (0.5, 0.60)),    # torso
            ((0.58, 0.33), (0.62, 0.02)),  # both arms reaching straight up
            ((0.42, 0.33), (0.38, 0.02)),
            ((0.5, 0.60), (0.48, 0.94)),   # standing leg
            ((0.5, 0.60), (0.64, 0.66)),   # raised bent knee
            ((0.64, 0.66), (0.58, 0.80)),
        ],
    },
    "B": {
        "head": (0.5, 0.12),
        "lines": [
            ((0.5, 0.20), (0.5, 0.55)),    # torso
            ((0.44, 0.25), (0.30, 0.04)),  # diagonal arm
            ((0.58, 0.25), (0.60, 0.00)),  # straight-up arm
            ((0.5, 0.55), (0.44, 0.92)),   # standing leg
            ((0.5, 0.55), (0.60, 0.72)),   # raised leg, tucked in close
            ((0.60, 0.72), (0.58, 0.86)),
        ],
    },
    "C": {
        "head": (0.40, 0.30),
        "lines": [
            ((0.40, 0.38), (0.42, 0.62)),  # torso
            ((0.40, 0.42), (0.74, 0.40)),  # arms reaching forward
            ((0.40, 0.46), (0.74, 0.46)),
            ((0.42, 0.62), (0.62, 0.66)),  # bent legs
            ((0.62, 0.66), (0.58, 0.92)),
            ((0.42, 0.62), (0.56, 0.70)),
            ((0.56, 0.70), (0.52, 0.92)),
        ],
    },
    "D": {
        "head": (0.5, 0.30),
        "lines": [
            ((0.5, 0.38), (0.5, 0.62)),    # torso, dropped low
            ((0.44, 0.42), (0.40, 0.62)),  # arms hanging...
            ((0.40, 0.62), (0.46, 0.88)),  # ...hands down to the floor
            ((0.56, 0.42), (0.60, 0.62)),
            ((0.60, 0.62), (0.54, 0.88)),
            ((0.5, 0.62), (0.28, 0.70)),   # knees pushed out past the feet
            ((0.28, 0.70), (0.38, 0.92)),
            ((0.5, 0.62), (0.72, 0.70)),
            ((0.72, 0.70), (0.62, 0.92)),
        ],
    },
}

POSE_FIGURES["E"] = {
    "head": (0.5, 0.12),
    "lines": [
        ((0.5, 0.20), (0.5, 0.55)),     # torso
        ((0.58, 0.25), (0.62, 0.00)),   # one arm shot straight up
        ((0.42, 0.25), (0.38, 0.58)),   # the other pressed down at the side
        ((0.5, 0.55), (0.47, 0.92)),    # feet together
        ((0.5, 0.55), (0.53, 0.92)),
    ],
}
POSE_FIGURES["F"] = {
    "head": (0.5, 0.12),
    "lines": [
        ((0.5, 0.20), (0.5, 0.55)),     # torso
        ((0.44, 0.24), (0.49, 0.02)),   # arms overhead, hands together
        ((0.56, 0.24), (0.51, 0.02)),
        ((0.5, 0.55), (0.5, 0.92)),     # standing leg
        ((0.5, 0.55), (0.68, 0.62)),    # bent leg, foot to knee
        ((0.68, 0.62), (0.53, 0.72)),
    ],
}
POSE_FIGURES["G"] = {
    "head": (0.5, 0.16),
    "lines": [
        ((0.5, 0.24), (0.5, 0.56)),     # torso
        ((0.56, 0.28), (0.72, 0.02)),   # bow arm aimed at the sky
        ((0.44, 0.28), (0.34, 0.20)),   # drawing arm: elbow up beside the head...
        ((0.34, 0.20), (0.46, 0.24)),   # ...then wrist back to the chin
        ((0.5, 0.56), (0.44, 0.92)),    # standing leg
        ((0.5, 0.56), (0.63, 0.70)),    # other leg lifted clear of the floor
        ((0.63, 0.70), (0.59, 0.81)),
    ],
}
POSE_FIGURES["H"] = {
    "head": (0.5, 0.12),
    "lines": [
        ((0.5, 0.20), (0.5, 0.55)),     # torso
        ((0.5, 0.55), (0.5, 0.92)),     # standing leg
        ((0.5, 0.55), (0.66, 0.42)),    # knee pulled up...
        ((0.66, 0.42), (0.64, 0.58)),   # ...ankle tucked down
        ((0.44, 0.26), (0.62, 0.40)),   # both hands hugging the knee
        ((0.56, 0.26), (0.66, 0.44)),
    ],
}

# The card already shows the pose name as its heading, so the caption is just
# the shape.
POSE_CAPTIONS = {
    "A": "Both arms to the sky, left knee up",
    "B": "Arms in a tilted X, right leg up",
    "C": "Bend low, arms straight forward",
    "D": "Crouch low, hands to the floor",
    "E": "One arm up, one arm pinned down",
    "F": "Foot on knee, hands up together",
    "G": "Aim at the sky, one leg up",
    "H": "Hug one knee to your chest",
}


def _draw_stick_figure(img, letter, x0, y0, size, color):
    fig = POSE_FIGURES[letter]
    hx, hy = fig["head"]
    thickness = max(2, int(size * 0.035))
    cv2.circle(img, (int(x0 + hx * size), int(y0 + hy * size)),
               max(3, int(size * 0.08)), color, thickness, cv2.LINE_AA)
    for (x1, y1), (x2, y2) in fig["lines"]:
        cv2.line(img, (int(x0 + x1 * size), int(y0 + y1 * size)),
                 (int(x0 + x2 * size), int(y0 + y2 * size)),
                 color, thickness, cv2.LINE_AA)


# Main-body landmark connections grouped by the body part names the pose
# scorers report, so each limb can be colored by its own score.
PART_SEGMENTS = {
    "left_arm": [(11, 13), (13, 15)],
    "right_arm": [(12, 14), (14, 16)],
    "torso": [(11, 12), (11, 23), (12, 24), (23, 24)],
    "left_leg": [(23, 25), (25, 27)],
    "right_leg": [(24, 26), (26, 28)],
}
NEUTRAL = (200, 200, 200)


def draw_skeleton(frame, landmarks, mirror: bool, part_scores=None, threshold: float = 1.0):
    """Hint mode: trace of the pose the AI detects for one person.

    With `part_scores` (dict of body part -> score), each limb is colored
    green if that part clears `threshold` and dark red if it doesn't; parts
    the pose doesn't care about stay neutral. Without it, the whole trace is
    neutral."""
    h, w = frame.shape[:2]

    def pt(i):
        x = (1.0 - landmarks[i].x) if mirror else landmarks[i].x
        return int(x * w), int(landmarks[i].y * h)

    for part, segments in PART_SEGMENTS.items():
        if part_scores is None or part not in part_scores:
            color = NEUTRAL
        else:
            color = GREEN if part_scores[part] >= threshold else DARK_RED
        for a, b in segments:
            cv2.line(frame, pt(a), pt(b), color, 3, cv2.LINE_AA)
        for i in {j for seg in segments for j in seg}:
            cv2.circle(frame, pt(i), 5, color, -1, cv2.LINE_AA)


def draw_info_hint(frame):
    h = frame.shape[0]
    cv2.putText(frame, "Press I for how to play - H for hint trace", (18, h - 18),
                FONT, 0.6, ACCENT, 1, cv2.LINE_AA)


def draw_info_overlay(frame, hold_seconds: float, confidence_threshold: float,
                      rounds=("ABCD", "EFGH"), mystery_rounds=()):
    """Full-screen overlay: the rules plus a diagram of each pose, one row
    of cards per (non-mystery) round."""
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), PANEL, -1)
    _blend(frame, overlay, 0.88)

    _put_centered(frame, "HOW TO PLAY", w / 2, h * 0.055, 1.2, ACCENT, 2)

    rules = [
        "1. Line up left to right - each adventurer is given one pose name",
        "2. Do your pose until your name turns GREEN",
        f"3. When ALL names are green, hold together for {hold_seconds:g} seconds",
        "4. Round 1 done? Harder poses unlock... and the final round is a MYSTERY:",
        f"   no name, just your glowing skeleton - find your secret pose and hold it {hold_seconds:g}s to lock in!",
        f"(The AI must be more than {confidence_threshold:.0%} sure your pose is right)",
    ]
    rounds = tuple(r for i, r in enumerate(rounds) if i not in set(mystery_rounds))
    y = h * 0.105
    for line in rules:
        _put_centered(frame, line, w / 2, y, 0.6, WHITE, 1)
        y += h * 0.038

    n_cols = max(len(r) for r in rounds)
    card_w = w / (n_cols + 1.6)
    gap = (w - n_cols * card_w) / (n_cols + 1)
    row_h = h * 0.31
    card_size = min(card_w * 0.72, row_h * 0.62)
    top0 = h * 0.335
    for row, letters in enumerate(rounds):
        top = top0 + row * row_h
        label = f"ROUND {row + 1}"
        cv2.putText(frame, label, (int(gap * 0.4), int(top + row_h * 0.5)), FONT,
                    0.6, ACCENT, 1, cv2.LINE_AA)
        for i, letter in enumerate(letters):
            x0 = gap + i * (card_w + gap)
            name = POSE_NAMES[letter]
            _put_centered(frame, name, x0 + card_w / 2, top + h * 0.02,
                          _fit_scale(name, card_w * 0.95, 0.95, 2), GREEN, 2)
            _draw_stick_figure(frame, letter, x0 + (card_w - card_size) / 2,
                               top + h * 0.05, card_size, WHITE)
            _put_centered(frame, POSE_CAPTIONS[letter], x0 + card_w / 2,
                          top + h * 0.055 + card_size + h * 0.025, 0.48, ACCENT, 1)

    _put_centered(frame, "Press I to close", w / 2, h * 0.97, 0.6, WHITE, 1)


def draw_round_complete(frame, next_round: int, mystery: bool = False):
    if mystery:
        draw_banner(frame, "Skill mastered!",
                    "Final round: your pose is a MYSTERY. Follow your skeleton and hold it!")
    else:
        draw_banner(frame, "Skill mastered!",
                    f"But the trial is not over... Round {next_round} begins. Get ready!")


def draw_complete(frame):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), PANEL, -1)
    _blend(frame, overlay, 0.65)
    _put_centered(frame, "MISSION COMPLETE", w / 2, h * 0.42, 2.2, GREEN, 5)
    _put_centered(frame, "Adventurers have mastered the required skill",
                  w / 2, h * 0.55, 1.0, WHITE, 2)
    _put_centered(frame, "Press R for a new trial - Q to quit", w / 2, h * 0.88, 0.7, ACCENT, 1)
