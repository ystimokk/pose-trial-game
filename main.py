"""Admin entry point for the Master your skills station.

Usage:
    python main.py --participants 3
"""

import argparse
from dataclasses import replace

from pose_trial.app import run
from pose_trial.config import AppConfig


def main():
    cfg = AppConfig()
    parser = argparse.ArgumentParser(description="Master your skills station")
    parser.add_argument(
        "-n", "--participants", type=int, default=None,
        help=f"Number of participants (1-{cfg.max_participants})",
    )
    parser.add_argument(
        "--dev", action="store_true",
        help="Dev mode: cycle all poses in order and auto-advance",
    )
    parser.add_argument(
        "--round", type=int, default=1,
        help="Start at this round (1-based), e.g. 3 for the mystery round",
    )
    parser.add_argument(
        "--camera", type=int, default=None,
        help=f"Camera index (default {cfg.camera_index}); try 1 if the picture is black",
    )
    parser.add_argument(
        "--list-cameras", action="store_true",
        help="Probe the attached cameras, report which ones give a picture, and exit",
    )
    args = parser.parse_args()

    if args.list_cameras:
        from pose_trial.app import list_cameras
        list_cameras(cfg)
        return

    if args.camera is not None:
        cfg = replace(cfg, camera_index=args.camera)

    n = args.participants
    while n is None or not (1 <= n <= cfg.max_participants):
        try:
            n = int(input(f"How many adventurers? (1-{cfg.max_participants}): "))
        except (ValueError, EOFError):
            n = None

    run(n, cfg, dev=args.dev, start_round=args.round)


if __name__ == "__main__":
    main()
