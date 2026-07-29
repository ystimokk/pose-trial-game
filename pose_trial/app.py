"""Main application loop and state machine.

States:
    LINEUP         -> waiting for n people to be in view
    DETECTED       -> short "Detected n adventurers..." interstitial
    TRIAL          -> pose code shown; letters turn green as poses are held;
                      when all are green a hold countdown runs
    ROUND_COMPLETE -> interstitial before the next (harder) round unlocks
    COMPLETE       -> final mission complete screen
"""

import random
import time
from enum import Enum, auto

import cv2

from .config import AppConfig
from .detector import PoseDetector
from .poses import NOSE, POSE_SCORERS
from . import ui


class State(Enum):
    LINEUP = auto()
    DETECTED = auto()
    TRIAL = auto()
    ROUND_COMPLETE = auto()
    COMPLETE = auto()


def generate_code(alphabet: str, n: int) -> str:
    return "".join(random.choice(alphabet) for _ in range(n))


class HoldClock:
    """Counts how long a pose has been held.

    Time accumulates ONLY on frames where the pose is actually good. A break
    shorter than the grace period pauses the clock (so detector jitter does
    not punish anyone); a longer break clears it. With grace at 0 any red
    frame resets the hold immediately.
    """

    def __init__(self, grace_seconds: float):
        self.grace = grace_seconds
        self.held = 0.0
        self._green_at = None   # previous green frame, or None if the last frame was red
        self._broke_at = None   # when the current red streak started

    def update(self, green: bool, now: float) -> float:
        if green:
            if self._green_at is not None:
                self.held += now - self._green_at
            self._green_at = now
            self._broke_at = None
        else:
            self._green_at = None
            if self._broke_at is None:
                self._broke_at = now
            if now - self._broke_at >= self.grace:
                self.held = 0.0
        return self.held

    def reset(self):
        self.held = 0.0
        self._green_at = None
        self._broke_at = None


def _sorted_left_to_right(people, mirror: bool):
    """Order detected people by their on-screen x position (left to right)."""
    def display_x(lm):
        cx = sum(p.x for p in lm) / len(lm)
        return 1.0 - cx if mirror else cx
    return sorted(people, key=display_x)


def list_cameras(cfg: AppConfig, max_index: int = 4) -> None:
    """Report which camera indices open and which actually produce a picture.

    Cameras ramp their exposure over the first frames, so sample a short run
    rather than judging the very first (usually dark) one.
    """
    print("Probing cameras...\n")
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.frame_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.frame_height)
        means = [f.mean() for _ in range(30) for ok, f in [cap.read()] if ok and f is not None]
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        if not means:
            print(f"  index {idx}: opens but returns no frames")
        elif max(means) < cfg.black_frame_threshold:
            print(f"  index {idx}: {w}x{h} - ALL BLACK (lens covered, camera busy, "
                  f"or this terminal lacks camera permission)")
        else:
            print(f"  index {idx}: {w}x{h} - working picture (brightness {max(means):.0f})")
    print(f"\nRun with --camera N to use a specific one (currently {cfg.camera_index}).")


def run(n: int, cfg: AppConfig | None = None, dev: bool = False, start_round: int = 1):
    """Run the station. In dev mode the code isn't random: trials walk through
    the alphabet in order (A, B, C, D, ...) and auto-advance after each
    completion, so every pose can be tested quickly. `start_round` (1-based)
    lets the admin skip straight to a later round for testing."""
    cfg = cfg or AppConfig()
    n = max(1, min(cfg.max_participants, n))

    detector = PoseDetector(cfg, num_poses=n)
    cap = cv2.VideoCapture(cfg.camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.frame_height)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {cfg.camera_index}")

    rounds = cfg.round_alphabets
    initial_round_idx = max(0, min(len(rounds) - 1, start_round - 1))
    round_idx = initial_round_idx
    dev_letters = "".join(dict.fromkeys("".join(rounds)))
    dev_index = 0
    solved = [False] * n          # mystery rounds: locked in after a full hold
    person_clocks = [HoldClock(cfg.break_grace_seconds) for _ in range(n)]

    def next_code() -> str:
        nonlocal dev_index
        if dev:
            letter = dev_letters[dev_index % len(dev_letters)]
            dev_index += 1
            return letter * n
        return generate_code(rounds[round_idx], n)

    code = next_code()
    print(f"Pose code for {n} adventurers: {code}")

    state = State.LINEUP
    lineup_full_since = None      # when n people first became visible
    detected_at = None            # when the DETECTED interstitial started
    hold = HoldClock(cfg.break_grace_seconds)  # group hold, green time only
    completed_at = None           # when the COMPLETE screen appeared
    round_complete_at = None      # when the ROUND_COMPLETE screen appeared
    show_info = False             # info overlay toggled with the I key
    show_hint = False             # skeleton trace toggled with the H key
    dark_since = None             # start of an unbroken run of black frames

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            now = time.monotonic()

            # Subsampled so this costs nothing; a covered or busy camera still
            # returns "valid" frames, they are just entirely black.
            if frame[::16, ::16].mean() < cfg.black_frame_threshold:
                if dark_since is None:
                    dark_since = now
            else:
                dark_since = None

            people = detector.detect(frame, int(now * 1000))
            people = _sorted_left_to_right(people, cfg.mirror_display)

            display = cv2.flip(frame, 1) if cfg.mirror_display else frame
            disp_h, disp_w = display.shape[:2]

            # In TRIAL the trace is drawn per-person in green/red instead
            if show_hint and state != State.TRIAL:
                for lm in people:
                    ui.draw_skeleton(display, lm, cfg.mirror_display)

            if state == State.LINEUP:
                if len(people) >= n:
                    lineup_full_since = lineup_full_since or now
                    if now - lineup_full_since >= cfg.lineup_stable_seconds:
                        state = State.DETECTED
                        detected_at = now
                else:
                    lineup_full_since = None
                ui.draw_lineup(display, len(people), n)

            elif state == State.DETECTED:
                ui.draw_detected(display, n)
                if now - detected_at >= cfg.detected_message_seconds:
                    state = State.TRIAL
                    hold.reset()

            elif state == State.TRIAL:
                mystery = not dev and round_idx in cfg.mystery_rounds
                statuses = [False] * n
                anchors = []
                for i, lm in enumerate(people[:n]):
                    letter = code[i]
                    result = POSE_SCORERS[letter](lm, cfg.tuning)
                    threshold = cfg.confidence_overrides.get(letter, cfg.confidence_threshold)
                    held = result.total > threshold
                    nose = lm[NOSE]
                    x = (1.0 - nose.x) * disp_w if cfg.mirror_display else nose.x * disp_w
                    if mystery:
                        if not solved[i]:
                            if person_clocks[i].update(held, now) >= cfg.hold_seconds:
                                solved[i] = True
                        statuses[i] = solved[i]
                        # The skeleton IS the puzzle feedback: always shown
                        ui.draw_skeleton(display, lm, cfg.mirror_display,
                                         result.parts, threshold)
                    else:
                        statuses[i] = held
                        if show_hint:
                            ui.draw_skeleton(display, lm, cfg.mirror_display,
                                             result.parts, threshold)
                    anchors.append((letter, statuses[i], x, nose.y * disp_h))

                if mystery:
                    def hold_state(i):
                        if solved[i] or person_clocks[i].held <= 0.0:
                            return None
                        return cfg.hold_seconds - person_clocks[i].held

                    strip_states = [(solved[i], hold_state(i)) for i in range(n)]
                    ui.draw_status_circles(display, strip_states, cfg.hold_seconds)
                    markers = [(a[2], a[3], solved[i], hold_state(i))
                               for i, a in enumerate(anchors)]
                    ui.draw_person_circles(display, markers, cfg.hold_seconds)
                    if all(solved):
                        if round_idx < len(rounds) - 1:
                            state = State.ROUND_COMPLETE
                            round_complete_at = now
                        else:
                            state = State.COMPLETE
                            completed_at = now
                else:
                    all_green = len(people) >= n and all(statuses)
                    elapsed = hold.update(all_green, now)

                    ui.draw_pose_code(display, list(code), statuses)
                    ui.draw_person_letters(display, anchors)

                    if elapsed >= cfg.hold_seconds:
                        if not dev and round_idx < len(rounds) - 1:
                            state = State.ROUND_COMPLETE
                            round_complete_at = now
                        else:
                            state = State.COMPLETE
                            completed_at = now
                    elif elapsed > 0.0:
                        ui.draw_countdown(display, cfg.hold_seconds - elapsed, cfg.hold_seconds)

            elif state == State.ROUND_COMPLETE:
                ui.draw_round_complete(display, round_idx + 2,
                                       mystery=(round_idx + 1) in cfg.mystery_rounds)
                if now - round_complete_at >= cfg.round_advance_seconds:
                    round_idx += 1
                    code = next_code()
                    print(f"Round {round_idx + 1} pose code: {code}")
                    state = State.TRIAL
                    hold.reset()
                    solved = [False] * n
                    for clock in person_clocks:
                        clock.reset()

            elif state == State.COMPLETE:
                ui.draw_complete(display)
                if dev and now - completed_at >= cfg.dev_advance_seconds:
                    code = next_code()
                    print(f"Dev mode - next pose code: {code}")
                    state = State.TRIAL
                    hold.reset()

            if show_info:
                ui.draw_info_overlay(display, cfg.hold_seconds, cfg.confidence_threshold,
                                     cfg.round_alphabets, cfg.mystery_rounds)
            else:
                ui.draw_info_hint(display)

            if dark_since is not None and now - dark_since >= cfg.black_frame_seconds:
                ui.draw_camera_warning(display, cfg.camera_index)

            cv2.imshow(cfg.window_name, display)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("i"):
                show_info = not show_info
            if key == ord("h"):
                show_hint = not show_hint
            if key == ord("r"):
                round_idx = initial_round_idx
                code = next_code()
                print(f"New pose code: {code}")
                state = State.TRIAL if dev else State.LINEUP
                lineup_full_since = None
                hold.reset()
                solved = [False] * n
                for clock in person_clocks:
                    clock.reset()
    finally:
        detector.close()
        cap.release()
        cv2.destroyAllWindows()
