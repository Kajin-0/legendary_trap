#!/usr/bin/env python3
"""Generate weak-line evidence reports for one song."""
from __future__ import annotations

import argparse
from pathlib import Path

from legendary_trap.failure_analysis import analyze

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("song_id")
    args = parser.parse_args()
    analyze(args.song_id, ROOT / "output" / args.song_id / "timing.json",
            ROOT / "work" / args.song_id / "asr-base.en.json",
            ROOT / "input" / "lyrics" / f"{args.song_id}.txt",
            ROOT / "reports" / f"{args.song_id}_analysis" / "failure_analysis.json",
            ROOT / "reports" / f"{args.song_id}_analysis" / "failure_analysis.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
