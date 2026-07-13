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


def _sorted_left_to_right(people, mirror: bool):
    """Order detected people by their on-screen x position (left to right)."""
    def display_x(lm):
        cx = sum(p.x for p in lm) / len(lm)
        return 1.0 - cx if mirror else cx
    return sorted(people, key=display_x)


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
    person_hold = [None] * n      # mystery rounds: per-person hold start times
    person_green = [None] * n     # mystery rounds: per-person last-green times

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
    hold_started_at = None        # when everyone first went green
    last_all_green_at = None      # for the break grace period
    completed_at = None           # when the COMPLETE screen appeared
    round_complete_at = None      # when the ROUND_COMPLETE screen appeared
    show_info = False             # info overlay toggled with the I key
    show_hint = False             # skeleton trace toggled with the H key

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            now = time.monotonic()
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
                    hold_started_at = None
                    last_all_green_at = None

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
                            if held:
                                person_green[i] = now
                                person_hold[i] = person_hold[i] or now
                                if now - person_hold[i] >= cfg.hold_seconds:
                                    solved[i] = True
                            elif person_green[i] is None or now - person_green[i] > cfg.break_grace_seconds:
                                person_hold[i] = None
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
                        if solved[i] or person_hold[i] is None:
                            return None
                        return cfg.hold_seconds - (now - person_hold[i])

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
                    if all_green:
                        last_all_green_at = now
                        hold_started_at = hold_started_at or now
                    elif last_all_green_at is None or now - last_all_green_at > cfg.break_grace_seconds:
                        hold_started_at = None

                    ui.draw_pose_code(display, list(code), statuses)
                    ui.draw_person_letters(display, anchors)

                    if hold_started_at is not None:
                        elapsed = now - hold_started_at
                        if elapsed >= cfg.hold_seconds:
                            if not dev and round_idx < len(rounds) - 1:
                                state = State.ROUND_COMPLETE
                                round_complete_at = now
                            else:
                                state = State.COMPLETE
                                completed_at = now
                        else:
                            ui.draw_countdown(display, cfg.hold_seconds - elapsed, cfg.hold_seconds)

            elif state == State.ROUND_COMPLETE:
                ui.draw_round_complete(display, round_idx + 2,
                                       mystery=(round_idx + 1) in cfg.mystery_rounds)
                if now - round_complete_at >= cfg.round_advance_seconds:
                    round_idx += 1
                    code = next_code()
                    print(f"Round {round_idx + 1} pose code: {code}")
                    state = State.TRIAL
                    hold_started_at = None
                    last_all_green_at = None
                    solved = [False] * n
                    person_hold = [None] * n
                    person_green = [None] * n

            elif state == State.COMPLETE:
                ui.draw_complete(display)
                if dev and now - completed_at >= cfg.dev_advance_seconds:
                    code = next_code()
                    print(f"Dev mode - next pose code: {code}")
                    state = State.TRIAL
                    hold_started_at = None
                    last_all_green_at = None

            if show_info:
                ui.draw_info_overlay(display, cfg.hold_seconds, cfg.confidence_threshold,
                                     cfg.round_alphabets, cfg.mystery_rounds)
            else:
                ui.draw_info_hint(display)

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
                hold_started_at = None
                last_all_green_at = None
                solved = [False] * n
                person_hold = [None] * n
                person_green = [None] * n
    finally:
        detector.close()
        cap.release()
        cv2.destroyAllWindows()
