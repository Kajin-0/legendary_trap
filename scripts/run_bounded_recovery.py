#!/usr/bin/env python3
"""Run the established distil-large-v3 recovery on declared bounded windows."""
from __future__ import annotations

import argparse
import json
import signal
import subprocess
import time
from pathlib import Path

from faster_whisper import WhisperModel

from legendary_trap.alignment import AcousticToken, align_tokens
from legendary_trap.lyrics import parse_lyrics

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "distil-whisper/distil-large-v3-ct2"
FFMPEG = ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffmpeg"

# The lines are the weak early passage identified by the base.en baseline;
# reliable neighboring lines are included as chronological acoustic context.
SONG_GROUPS = {
  "slidin": {
    "early_line_001": {
        "start": 3.0,
        "end": 10.5,
        "line_ids": ["section_002_line_001", "section_002_line_002"],
    },
    "early_lines_002_004": {
        "start": 9.0,
        "end": 20.5,
        "line_ids": ["section_002_line_001", "section_002_line_002", "section_002_line_003",
                     "section_002_line_004"],
    },
    "early_lines_005_006": {
        "start": 18.5,
        "end": 28.8,
        "line_ids": ["section_002_line_005", "section_002_line_006", "section_003_line_001",
                     "section_003_line_002"],
    },
    "early_lines_003_001_005": {
        "start": 24.5,
        "end": 31.0,
        "line_ids": [
            "section_003_line_001", "section_003_line_002", "section_003_line_003",
            "section_003_line_004", "section_003_line_005",
        ],
    },
  },
  "you_missed_it": {
    "early_passage": {
      "start": 10.0,
      "end": 31.0,
      "line_ids": [f"section_002_line_{index:03d}" for index in range(1, 7)],
    },
  },
  "we_got_chemistry": {
    "early_passage": {
      "start": 0.0,
      "end": 36.0,
      "line_ids": [
        *[f"section_001_line_{index:03d}" for index in range(1, 11)],
        "section_002_line_001",
      ],
    },
    "outro_passage": {
      "start": 208.0,
      "end": 240.0,
      "line_ids": [
        *[f"section_006_line_{index:03d}" for index in range(1, 14)],
        *[f"section_007_line_{index:03d}" for index in range(1, 14)],
      ],
    },
  },
  "off_the_wave": {
    "intro_passage": {
      "start": 0.0,
      "end": 15.5,
      "line_ids": ["section_001_line_001", "section_001_line_002",
                   "section_001_line_003", "section_001_line_004"],
    },
  },
  "commin_long_ways": {
    "early_passage": {
      "start": 0.0,
      "end": 36.0,
      "line_ids": [
        *[f"section_001_line_{index:03d}" for index in range(1, 5)],
        *[f"section_002_line_{index:03d}" for index in range(1, 9)],
      ],
    },
    "late_passage": {
      "start": 130.0,
      "end": 162.84,
      "line_ids": [f"section_007_line_{index:03d}" for index in range(1, 5)],
    },
  },
  "chokehold": {
    "intro_passage": {
      "start": 0.0,
      "end": 16.0,
      "line_ids": ["section_001_line_001", "section_002_line_001",
                   "section_002_line_002", "section_003_line_001"],
    },
    "outro_passage": {
      "start": 124.0,
      "end": 130.032,
      "line_ids": [f"section_006_line_{index:03d}" for index in range(1, 5)],
    },
  },
}


class WindowTimeout(RuntimeError):
    pass


def _alarm(_signum, _frame):
    raise WindowTimeout("bounded distil-large-v3 window exceeded 5 minutes")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("song_id", choices=sorted(SONG_GROUPS))
    args = parser.parse_args()
    song_id = args.song_id
    groups_config = SONG_GROUPS[song_id]
    parsed = parse_lyrics(ROOT / "input/lyrics" / f"{song_id}.txt", song_id)
    by_id = {line.line_id: line for line in parsed.lines}
    audio = ROOT / "input/audio" / f"{song_id}.mp3"
    work = ROOT / "work" / song_id / "large_whisper"
    work.mkdir(parents=True, exist_ok=True)
    model_started = time.perf_counter()
    model = WhisperModel(MODEL_ID, device="cpu", compute_type="int8")
    load_seconds = time.perf_counter() - model_started
    groups = []
    total_started = time.perf_counter()
    for group_id, group in groups_config.items():
        start, end = float(group["start"]), float(group["end"])
        clip = work / f"{group_id}.wav"
        subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", str(start), "-to", str(end),
                        "-i", str(audio), "-ac", "1", "-ar", "16000", str(clip)],
                       check=True, timeout=60)
        inference_started = time.perf_counter()
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(300)
        try:
            segments, info = model.transcribe(
                str(clip), language="en", beam_size=5, word_timestamps=True,
                condition_on_previous_text=False, vad_filter=False, temperature=0.0,
                initial_prompt=None,
            )
            serialized, acoustic = [], []
            for segment in segments:
                words = []
                for word in segment.words or []:
                    row = {"text": word.word.strip(), "start": round(start + word.start, 4),
                           "end": round(start + word.end, 4), "probability": word.probability}
                    if row["text"]:
                        words.append(row)
                        acoustic.append(AcousticToken(**row))
                serialized.append({"start": round(start + segment.start, 4),
                                   "end": round(start + segment.end, 4), "text": segment.text,
                                   "avg_logprob": segment.avg_logprob,
                                   "no_speech_prob": segment.no_speech_prob, "words": words})
        finally:
            signal.alarm(0)
        auth = [token for line_id in group["line_ids"] for token in by_id[line_id].tokens]
        matches, coverage, unresolved = align_tokens(auth, acoustic)
        lines, offset = [], 0
        for line_id in group["line_ids"]:
            line = by_id[line_id]
            found = [matches[index] for index in range(offset, offset + len(line.tokens)) if index in matches]
            words = [{"text": word.text, "start": word.start, "end": word.end,
                      "probability": word.probability, "timing_source": "asr_distil_large_v3",
                      "acoustic_support": True} for word in found]
            lines.append({"line_id": line_id, "authoritative_text": line.original_text,
                          "lead_text": line.lead_text, "matched_tokens": len(found),
                          "total_tokens": len(line.tokens),
                          "coverage": len(found) / len(line.tokens) if line.tokens else 1.0,
                          "start": min((word.start for word in found), default=None),
                          "end": max((word.end for word in found), default=None),
                          "probability_mean": sum(word.probability for word in found) / len(found) if found else 0.0,
                          "words": words})
            offset += len(line.tokens)
        groups.append({"group_id": group_id, "window": [start, end], "line_ids": group["line_ids"],
                       "load_seconds": load_seconds, "inference_seconds": time.perf_counter() - inference_started,
                       "language": info.language, "language_probability": info.language_probability,
                       "segments": serialized, "asr_word_count": len(acoustic),
                       "authoritative_token_count": len(auth), "matched_tokens": len(matches),
                       "coverage": coverage, "unresolved_tokens": unresolved, "lines": lines})
    result = {"song_id": song_id, "model": MODEL_ID, "device": "cpu", "compute_type": "int8",
              "beam_size": 5, "prompting": False, "load_seconds": load_seconds,
              "runtime_seconds": time.perf_counter() - total_started, "groups": groups}
    (work / "groups.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"model": MODEL_ID, "load_seconds": load_seconds,
                      "runtime_seconds": result["runtime_seconds"],
                      "groups": [{"group_id": row["group_id"], "inference_seconds": row["inference_seconds"],
                                  "asr_word_count": row["asr_word_count"], "coverage": row["coverage"]}
                                 for row in groups]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
