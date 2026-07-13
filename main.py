"""Admin entry point for the Pose Trial station.

Usage:
    python main.py --participants 3
"""

import argparse

from pose_trial.app import run
from pose_trial.config import AppConfig


def main():
    cfg = AppConfig()
    parser = argparse.ArgumentParser(description="Pose Trial station")
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
    args = parser.parse_args()

    n = args.participants
    while n is None or not (1 <= n <= cfg.max_participants):
        try:
            n = int(input(f"How many adventurers? (1-{cfg.max_participants}): "))
        except (ValueError, EOFError):
            n = None

    run(n, cfg, dev=args.dev, start_round=args.round)


if __name__ == "__main__":
    main()
