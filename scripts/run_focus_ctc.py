#!/usr/bin/env python3
"""Run bounded CTC forced alignment on the three FOCUS lead-line groups."""
from __future__ import annotations

import json
import time
from pathlib import Path

from legendary_trap.ctc_alignment import align_audio_window

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    timing = json.loads((ROOT / "reports/focus_baseline/timing.json").read_text())
    sections = timing["sections"]
    by_id = {line["line_id"]: line for section in sections for line in section["lines"]}
    groups = {
        "intro": ["section_001_line_003", "section_001_line_004", "section_001_line_005", "section_001_line_006"],
        "early_chorus": [f"section_002_line_{i:03d}" for i in range(1, 8)],
        "outro": ["section_009_line_002", "section_009_line_003", "section_009_line_005",
                  "section_009_line_007", "section_009_line_008", "section_009_line_010"],
    }
    results = []
    started = time.perf_counter()
    for group_id, line_ids in groups.items():
        first, last = by_id[line_ids[0]], by_id[line_ids[-1]]
        start = max(0.0, first["start"] - 2.0)
        end = min(float(timing["audio"]["duration_seconds"]), last["end"] + 2.0)
        transcript = " ".join(by_id[line_id]["lead_text"] for line_id in line_ids if by_id[line_id]["lead_text"].strip())
        result = align_audio_window(ROOT / "input/audio/focus.mp3", transcript, start, end)
        result.update({"group_id": group_id, "line_ids": line_ids, "window_start": start, "window_end": end})
        results.append(result)
    output = ROOT / "work/focus/ctc/groups.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"runtime_seconds": time.perf_counter() - started, "groups": results}, indent=2) + "\n")
    print(json.dumps({"runtime_seconds": time.perf_counter() - started,
                      "groups": [{"group_id": r["group_id"], "window": [r["window_start"], r["window_end"]],
                                  "word_count": r["word_count"], "mean_word_confidence": r["mean_word_confidence"]} for r in results]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
