#!/usr/bin/env python3
"""Calibrate teacher-forced Whisper attention on known FOCUS lines only."""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import soundfile as sf
import whisper

from legendary_trap.whisper_attention_alignment import align_known_text

ROOT = Path(__file__).resolve().parents[1]


def direct_words(line: dict) -> list[dict]:
    return [w for w in line["words"] if w.get("acoustic_supported") and w.get("timing_source") == "asr"]


def bounds_for(lines: list[dict], index: int, duration: float) -> tuple[float, float] | None:
    prior = [direct_words(x) for x in lines[:index] if x["lead_text"] and direct_words(x)]
    following = [direct_words(x) for x in lines[index + 1:] if x["lead_text"] and direct_words(x)]
    if not prior:
        return None
    left = max(w["end"] for w in prior[-1])
    right = min(w["start"] for w in following[0]) if following else duration
    return left, min(duration, max(left + 0.75, right))


def main() -> int:
    audio, sample_rate = sf.read(ROOT / "work/focus/onset_fallback/focus.wav", dtype="float32")
    timing = json.loads((ROOT / "reports/focus_final/timing.json").read_text())
    lines = [line for section in timing["sections"] for line in section["lines"]]
    eligible = []
    for index, line in enumerate(lines):
        direct = direct_words(line)
        bounds = bounds_for(lines, index, len(audio) / sample_rate)
        if line["lead_text"] and line["confidence"] >= 0.85 and direct and bounds and bounds[1] - bounds[0] >= 0.75:
            eligible.append((index, line, direct, bounds))
    selected = [eligible[round(i * (len(eligible) - 1) / 19)] for i in range(20)]
    model_started = time.perf_counter()
    model = whisper.load_model("turbo", device="cpu", download_root=None, in_memory=False)
    load_seconds = time.perf_counter() - model_started
    rows = []
    for index, line, direct, bounds in selected:
        start_sample, end_sample = round(bounds[0] * sample_rate), round(bounds[1] * sample_rate)
        result = align_known_text(model, line["lead_text"], audio[start_sample:end_sample], sample_rate, bounds[0])
        reference = min(w["start"] for w in direct)
        predicted = result["words"][0]["start"] if result["words"] else None
        rows.append({"line_id": line["line_id"], "text": line["lead_text"], "window": list(bounds),
                     "reference_start": reference, "prediction": result,
                     "absolute_error_ms": abs(predicted - reference) * 1000 if predicted is not None else None})
    # Wrong-word controls use the same window and full audio evidence, changing only
    # the teacher-forced lexical candidate. This is diagnostic, never output text.
    controls = []
    for index, line, direct, bounds in selected[:8]:
        start_sample, end_sample = round(bounds[0] * sample_rate), round(bounds[1] * sample_rate)
        correct = align_known_text(model, line["lead_text"], audio[start_sample:end_sample], sample_rate, bounds[0])
        first = line["lead_text"].split()[0]
        wrong_word = "yeah" if first.lower().strip(".,!?…") != "yeah" else "focus"
        wrong = align_known_text(model, wrong_word, audio[start_sample:end_sample], sample_rate, bounds[0])
        correct_probability = correct["words"][0]["probability"] if correct["words"] else 0.0
        wrong_probability = wrong["words"][0]["probability"] if wrong["words"] else 0.0
        controls.append({"line_id": line["line_id"], "correct_word": first, "wrong_word": wrong_word,
                         "correct_probability": correct_probability, "wrong_probability": wrong_probability,
                         "probability_margin": correct_probability - wrong_probability,
                         "correct": correct, "wrong": wrong})
    errors = [row["absolute_error_ms"] for row in rows if row["absolute_error_ms"] is not None]
    margins = [row["probability_margin"] for row in controls]
    probabilities = [row["prediction"]["words"][0]["probability"] for row in rows if row["prediction"]["words"]]
    ordered = sorted(errors)
    calibration = {"n": len(errors), "median_absolute_error_ms": statistics.median(errors),
                   "mean_absolute_error_ms": statistics.mean(errors),
                   "p90_absolute_error_ms": ordered[min(len(ordered) - 1, round(.9 * (len(ordered) - 1)))],
                   "max_error_ms": max(errors), "success_le_100ms": sum(x <= 100 for x in errors),
                   "success_le_150ms": sum(x <= 150 for x in errors), "success_le_250ms": sum(x <= 250 for x in errors),
                   "median_word_probability": statistics.median(probabilities),
                   "probability_distribution": probabilities,
                   "probability_margin_distribution": margins,
                   "calibration_passed": statistics.median(errors) <= 150 and ordered[min(len(ordered) - 1, round(.9 * (len(ordered) - 1)))] <= 300}
    out = ROOT / "reports/focus_attention_alignment"
    out.mkdir(parents=True, exist_ok=True)
    (out / "environment.json").write_text(json.dumps({"openai_whisper": whisper.__version__, "model": "turbo", "device": "cpu", "torch": __import__('torch').__version__, "load_seconds": load_seconds}, indent=2) + "\n")
    (out / "calibration.json").write_text(json.dumps({**calibration, "rows": rows}, indent=2) + "\n")
    (out / "lexical_controls.json").write_text(json.dumps({"n": len(controls), "correct_over_wrong": sum(x["probability_margin"] > 0 for x in controls) / len(controls), "controls": controls}, indent=2) + "\n")
    (out / "diagnostics.json").write_text(json.dumps({"window_policy": "previous direct end to next direct start, minimum 0.75 seconds", "attention_concentration": "not exposed by upstream find_alignment", "load_seconds": load_seconds}, indent=2) + "\n")
    (out / "summary.json").write_text(json.dumps(calibration, indent=2) + "\n")
    (out / "calibration.md").write_text("# Whisper attention calibration\n\n" + json.dumps(calibration, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
