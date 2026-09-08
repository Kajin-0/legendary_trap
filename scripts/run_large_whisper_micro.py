#!/usr/bin/env python3
"""Bounded distil-large-v3 micro-benchmark on one unresolved FOCUS window."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "distil-whisper/distil-large-v3-ct2"
WINDOW_START = 4.8
WINDOW_END = 19.62


def main() -> int:
    started = time.perf_counter()
    model_started = time.perf_counter()
    model = WhisperModel(MODEL_ID, device="cpu", compute_type="int8")
    model_load_seconds = time.perf_counter() - model_started
    inference_started = time.perf_counter()
    segments, info = model.transcribe(
        str(ROOT / "work/focus/large_whisper/early_micro.wav"),
        beam_size=5,
        language="en",
        word_timestamps=True,
        condition_on_previous_text=False,
        vad_filter=False,
        temperature=0.0,
        initial_prompt=None,
    )
    serialized = []
    for segment in segments:
        words = []
        for word in segment.words or []:
            words.append({
                "text": word.word,
                "start": round(WINDOW_START + word.start, 4),
                "end": round(WINDOW_START + word.end, 4),
                "probability": word.probability,
            })
        serialized.append({"start": round(WINDOW_START + segment.start, 4),
                           "end": round(WINDOW_START + segment.end, 4),
                           "text": segment.text, "avg_logprob": segment.avg_logprob,
                           "no_speech_prob": segment.no_speech_prob, "words": words})
    result = {
        "model": MODEL_ID,
        "compute_type": "int8",
        "device": "cpu",
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "audio": "work/focus/large_whisper/early_micro.wav",
        "load_seconds": model_load_seconds,
        "inference_seconds": time.perf_counter() - inference_started,
        "total_seconds": time.perf_counter() - started,
        "language": info.language,
        "language_probability": info.language_probability,
        "duration_seconds": info.duration,
        "segments": serialized,
        "asr_word_count": sum(len(x["words"]) for x in serialized),
        "cache_dir": os.environ.get("HF_HOME", "default Hugging Face cache"),
    }
    output = ROOT / "work/focus/large_whisper/micro.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("model", "load_seconds", "inference_seconds", "total_seconds", "asr_word_count")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
