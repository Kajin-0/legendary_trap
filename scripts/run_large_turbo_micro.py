#!/usr/bin/env python3
"""One bounded large-v3-turbo comparison on the early FOCUS window."""
from __future__ import annotations

import json
import time
from pathlib import Path

from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    started = time.perf_counter()
    load_started = time.perf_counter()
    model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
    load_seconds = time.perf_counter() - load_started
    inference_started = time.perf_counter()
    segments, info = model.transcribe(
        str(ROOT / "work/focus/large_whisper/early_micro.wav"),
        beam_size=5, language="en", word_timestamps=True,
        condition_on_previous_text=False, vad_filter=False, temperature=0.0,
        initial_prompt=None,
    )
    rows = []
    for segment in segments:
        rows.append({"start": segment.start + 4.8, "end": segment.end + 4.8,
                     "text": segment.text, "avg_logprob": segment.avg_logprob,
                     "words": [{"text": w.word, "start": w.start + 4.8, "end": w.end + 4.8,
                                "probability": w.probability} for w in segment.words or []]})
    result = {"model": "large-v3-turbo", "device": "cpu", "compute_type": "int8",
              "window": [4.8, 19.62], "load_seconds": load_seconds,
              "inference_seconds": time.perf_counter() - inference_started,
              "total_seconds": time.perf_counter() - started, "language": info.language,
              "language_probability": info.language_probability, "segments": rows,
              "asr_word_count": sum(len(x["words"]) for x in rows)}
    out = ROOT / "work/focus/large_whisper/turbo_micro.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("model", "load_seconds", "inference_seconds", "total_seconds", "asr_word_count")}, indent=2))
