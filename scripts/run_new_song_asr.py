#!/usr/bin/env python3
"""Run one unhinted word-timestamp ASR pass for a newly prepared song."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from faster_whisper import WhisperModel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(args.audio), language="en", beam_size=5, best_of=1, temperature=0.0,
        word_timestamps=True, condition_on_previous_text=False, vad_filter=False,
        initial_prompt=None,
    )
    rows = []
    for segment in segments:
        rows.append({
            "start": float(segment.start), "end": float(segment.end),
            "text": segment.text.strip(),
            "avg_logprob": getattr(segment, "avg_logprob", None),
            "no_speech_prob": getattr(segment, "no_speech_prob", None),
            "words": [{
                "text": word.word.strip(), "start": float(word.start),
                "end": float(word.end), "probability": float(word.probability),
            } for word in (segment.words or []) if word.word.strip()],
        })
    result = {
        "model": "large-v3-turbo", "device": "cpu", "compute_type": "int8",
        "language": info.language, "language_probability": info.language_probability,
        "segments": rows, "runtime_seconds": time.perf_counter() - started,
        "word_count": sum(len(row["words"]) for row in rows),
        "unhinted": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("model", "runtime_seconds", "word_count")}, indent=2))


if __name__ == "__main__":
    main()
