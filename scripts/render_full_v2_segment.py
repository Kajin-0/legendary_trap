"""Render one resumable full-song v2 segment with master-time palette phase."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from legendary_trap.visualizer import render_preview

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("song_id")
    parser.add_argument("output", type=Path)
    parser.add_argument("--palette-offset", type=float, required=True)
    parser.add_argument("--timeout", type=int, default=2400)
    args = parser.parse_args()
    duration = float(json.loads((ROOT / "output" / args.song_id / "timing.json").read_text())
                     ["audio"]["duration_seconds"])
    result = render_preview(
        args.song_id, "trap_polar_350_artistlockup", 0.0, duration,
        timeout_seconds=args.timeout, lyric_font="Barlow Condensed",
        lyric_size=90, low_max_hz=350.0, identity_enabled=True,
        output_path=(ROOT / args.output), palette_time_offset=args.palette_offset,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
