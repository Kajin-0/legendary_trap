#!/usr/bin/env python3
"""Bounded singing-aligner micro-benchmark for FOCUS section 2."""
import json
from pathlib import Path

from legendary_trap.singing_alignment import align_window

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    result = align_window(ROOT / "input/audio/focus.mp3",
                          ["Focus,", "tears", "in", "my", "eyes", "but", "I", "hide", "that", "shit",
                           "Whole", "world", "movin’", "on", "but", "I’m", "stuck", "with", "it",
                           "Late", "nights", "starin’", "at", "the", "roof", "can’t", "quit",
                           "Tryna", "find", "myself", "while", "I’m", "losin’", "it",
                           "Focus", "focus", "I", "can’t", "fall", "apart"], 4.8, 19.62)
    out = ROOT / "work/focus/singing_aligner/micro.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("window_start", "window_end", "phoneme_count", "supported_phonemes", "phoneme_acoustic_coverage", "model_runtime_seconds")}, indent=2))
