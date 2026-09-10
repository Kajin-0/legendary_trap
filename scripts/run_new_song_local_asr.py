#!/usr/bin/env python3
"""Run one bounded, unhinted ASR pass over a weak local window."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = ROOT / "tools/ffmpeg-7.0.2-amd64-static/ffmpeg"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("start", type=float)
    parser.add_argument("duration", type=float)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="new_song_local_asr_") as tmp:
        clip = Path(tmp) / "window.wav"
        subprocess.run([
            str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error", "-ss", str(args.start),
            "-t", str(args.duration), "-i", str(args.audio), "-ar", "16000", "-ac", "1",
            str(clip),
        ], check=True, timeout=120)
        started = time.perf_counter()
        model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
        segments, info = model.transcribe(
            str(clip), language="en", beam_size=5, best_of=1, temperature=0.0,
            word_timestamps=True, condition_on_previous_text=False, vad_filter=False,
            initial_prompt=None,
        )
        rows = []
        for segment in segments:
            rows.append({
                "start": args.start + float(segment.start),
                "end": args.start + float(segment.end),
                "text": segment.text.strip(),
                "words": [
                    {"text": word.word.strip(), "start": args.start + float(word.start),
                     "end": args.start + float(word.end), "probability": float(word.probability)}
                    for word in (segment.words or []) if word.word.strip()
                ],
            })
    result = {
        "model": "large-v3-turbo", "unhinted": True, "start": args.start,
        "duration": args.duration, "language": info.language,
        "language_probability": info.language_probability, "segments": rows,
        "runtime_seconds": time.perf_counter() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
