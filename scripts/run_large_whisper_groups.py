#!/usr/bin/env python3
"""Run distil-large-v3 on only the three unresolved FOCUS regions."""
from __future__ import annotations

import json
import signal
import time
from pathlib import Path

from faster_whisper import WhisperModel

from legendary_trap.alignment import AcousticToken, align_tokens
from legendary_trap.lyrics import parse_lyrics

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "distil-whisper/distil-large-v3-ct2"
GROUPS = {
    "intro": (0.0, 7.21, ["section_001_line_003", "section_001_line_004", "section_001_line_005", "section_001_line_006"]),
    "early_section": (4.08, 33.58, [f"section_002_line_{i:03d}" for i in range(1, 9)]),
    "outro": (218.17, 240.024, ["section_009_line_002", "section_009_line_003", "section_009_line_005", "section_009_line_007", "section_009_line_008", "section_009_line_010"]),
}


class GroupTimeout(RuntimeError):
    pass


def _raise_group_timeout(_signum, _frame):
    raise GroupTimeout("single group inference exceeded 5 minutes")


def main() -> int:
    parsed = parse_lyrics(ROOT / "input/lyrics/focus.txt", "focus")
    by_id = {line.line_id: line for line in parsed.lines}
    model_started = time.perf_counter()
    model = WhisperModel(MODEL_ID, device="cpu", compute_type="int8")
    load_seconds = time.perf_counter() - model_started
    results = []
    started = time.perf_counter()
    for group_id, (start, end, line_ids) in GROUPS.items():
        audio_path = ROOT / "work/focus/large_whisper" / f"{group_id}.wav"
        inference_started = time.perf_counter()
        signal.signal(signal.SIGALRM, _raise_group_timeout)
        signal.alarm(300)
        try:
            segments, info = model.transcribe(
                str(audio_path), beam_size=5, language="en", word_timestamps=True,
                condition_on_previous_text=False, vad_filter=False, temperature=0.0,
                initial_prompt=None,
            )
        finally:
            signal.alarm(0)
        serialized = []
        acoustic = []
        for segment in segments:
            words = []
            for word in segment.words or []:
                row = {"text": word.word, "start": round(start + word.start, 4),
                       "end": round(start + word.end, 4), "probability": word.probability}
                words.append(row)
                acoustic.append(AcousticToken(row["text"], row["start"], row["end"], row["probability"]))
            serialized.append({"start": round(start + segment.start, 4), "end": round(start + segment.end, 4),
                               "text": segment.text, "avg_logprob": segment.avg_logprob,
                               "no_speech_prob": segment.no_speech_prob, "words": words})
        auth = [token for line_id in line_ids for token in by_id[line_id].tokens]
        matches, coverage, unresolved = align_tokens(auth, acoustic)
        line_rows = []
        offset = 0
        for line_id in line_ids:
            line = by_id[line_id]
            found = [matches[i] for i in range(offset, offset + len(line.tokens)) if i in matches]
            similarities = len(found) / len(line.tokens) if line.tokens else 1.0
            line_rows.append({"line_id": line_id, "authoritative_text": line.original_text,
                              "lead_text": line.lead_text, "matched_tokens": len(found),
                              "total_tokens": len(line.tokens), "coverage": similarities,
                              "start": min((x.start for x in found), default=None),
                              "end": max((x.end for x in found), default=None),
                              "probability_mean": sum(x.probability for x in found) / len(found) if found else 0.0,
                              "words": [{"text": x.text, "start": x.start, "end": x.end,
                                         "probability": x.probability, "timing_source": "asr_distil_large_v3",
                                         "acoustic_support": True} for x in found]})
            offset += len(line.tokens)
        results.append({"group_id": group_id, "window": [start, end], "line_ids": line_ids,
                        "load_seconds": load_seconds, "inference_seconds": time.perf_counter() - inference_started,
                        "language": info.language, "language_probability": info.language_probability,
                        "segments": serialized, "asr_word_count": len(acoustic),
                        "authoritative_token_count": len(auth), "matched_tokens": len(matches),
                        "coverage": coverage, "unresolved_tokens": unresolved, "lines": line_rows})
    output = ROOT / "work/focus/large_whisper/groups.json"
    output.write_text(json.dumps({"model": MODEL_ID, "load_seconds": load_seconds,
                                  "runtime_seconds": time.perf_counter() - started, "groups": results}, indent=2) + "\n")
    print(json.dumps({"model": MODEL_ID, "load_seconds": load_seconds,
                      "runtime_seconds": time.perf_counter() - started,
                      "groups": [{"group_id": x["group_id"], "inference_seconds": x["inference_seconds"],
                                  "asr_word_count": x["asr_word_count"], "coverage": x["coverage"]} for x in results]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
