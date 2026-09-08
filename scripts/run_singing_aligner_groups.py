#!/usr/bin/env python3
"""Run the three bounded FOCUS singing-aligner groups."""
import json
import time
from pathlib import Path

from legendary_trap.singing_alignment import align_window

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    groups = {
        "intro": (0.0, 7.21, ["Woah", "Focus", "Pain", "in", "my", "heart", "focus"]),
        "early_section": (4.8, 19.62, ["Focus", "tears", "in", "my", "eyes", "but", "I", "hide", "that", "shit",
                                           "Whole", "world", "movin’", "on", "but", "I’m", "stuck", "with", "it",
                                           "Late", "nights", "starin’", "at", "the", "roof", "can’t", "quit",
                                           "Tryna", "find", "myself", "while", "I’m", "losin’", "it",
                                           "Focus", "focus", "I", "can’t", "fall", "apart"]),
        "outro": (218.17, 240.024, ["Yeah", "Keep", "movin’", "Even", "when", "it", "hurts", "One", "more", "step",
                                      "One", "more", "day", "Focus"]),
    }
    started = time.perf_counter()
    results = []
    for group_id, (start, end, words) in groups.items():
        result = align_window(ROOT / "input/audio/focus.mp3", words, start, end)
        result["group_id"] = group_id
        results.append(result)
    output = ROOT / "work/focus/singing_aligner/groups.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"runtime_seconds": time.perf_counter() - started, "groups": results}, indent=2) + "\n")
    print(json.dumps({"runtime_seconds": time.perf_counter() - started,
                      "groups": [{"group_id": x["group_id"], "phoneme_coverage": x["phoneme_acoustic_coverage"],
                                  "runtime": x["model_runtime_seconds"]} for x in results]}, indent=2))
