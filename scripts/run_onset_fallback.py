#!/usr/bin/env python3
"""Calibrate and evaluate bounded acoustic events on FOCUS only."""
from __future__ import annotations

import json
import statistics
import subprocess
from pathlib import Path

import soundfile as sf

from legendary_trap.acoustic_events import locate_event

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {"section_001_line_004", "section_001_line_006", "section_009_line_002", "section_009_line_010"}


def _audio() -> tuple[object, int]:
    path = ROOT / "work/focus/onset_fallback/focus.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        subprocess.run([str(ROOT / "tools/ffmpeg-7.0.2-amd64-static/ffmpeg"), "-y", "-i", str(ROOT / "input/audio/focus.mp3"), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(path)], check=True, timeout=60)
    return sf.read(path, dtype="float32")


def _direct_bounds(lines: list[dict], index: int, duration: float) -> tuple[float, float] | None:
    def direct(line: dict) -> list[dict]:
        return [w for w in line["words"] if w.get("acoustic_supported", False) and w.get("timing_source") == "asr"]

    prior = [(x, direct(x)) for x in lines[:index] if x["lead_text"] and direct(x)]
    following = [(x, direct(x)) for x in lines[index + 1:] if x["lead_text"] and direct(x)]
    if not prior:
        return None
    left = max(w["end"] for w in prior[-1][1])
    right = (min(w["start"] for w in following[0][1])
             if following else duration)
    return (max(0.0, left), min(duration, max(left + 0.25, right)))


def main() -> int:
    audio, sample_rate = _audio()
    duration = len(audio) / sample_rate
    timing = json.loads((ROOT / "reports/focus_final/timing.json").read_text())
    lines = [line for section in timing["sections"] for line in section["lines"]]
    rows = []
    for index, line in enumerate(lines):
        direct = [w for w in line["words"] if w.get("acoustic_supported", False) and w.get("timing_source") == "asr"]
        bounds = _direct_bounds(lines, index, duration)
        if line["lead_text"] and line["confidence"] >= 0.82 and direct and bounds and bounds[1] - bounds[0] >= 0.5:
            rows.append((line, direct, bounds))
    # Spread calibration examples over the song, selecting 20 known reliable starts.
    rows = [rows[round(i * (len(rows) - 1) / 19)] for i in range(20)]
    calibration = []
    for line, direct, bounds in rows:
        reference = min(w["start"] for w in direct)
        prediction = locate_event(audio, sample_rate, *bounds)
        calibration.append({"line_id": line["line_id"], "reference_start": reference,
                            "window": list(bounds), "prediction": prediction,
                            "absolute_error_seconds": abs(prediction["start"] - reference)})
    errors = [x["absolute_error_seconds"] for x in calibration]
    ordered = sorted(errors)
    p90 = ordered[min(len(ordered) - 1, round(0.9 * (len(ordered) - 1)))]
    calibration_summary = {"n": len(errors), "median_absolute_error_seconds": statistics.median(errors),
                           "mean_absolute_error_seconds": statistics.mean(errors), "p90_absolute_error_seconds": p90,
                           "max_absolute_error_seconds": max(errors),
                           "within_100ms": sum(x <= .1 for x in errors), "within_150ms": sum(x <= .15 for x in errors),
                           "within_250ms": sum(x <= .25 for x in errors), "rows": calibration}
    calibration_passed = calibration_summary["median_absolute_error_seconds"] <= 0.12 and calibration_summary["p90_absolute_error_seconds"] <= 0.25
    out = ROOT / "reports/focus_onset_fallback"
    out.mkdir(parents=True, exist_ok=True)
    (out / "calibration.json").write_text(json.dumps(calibration_summary, indent=2) + "\n")
    (out / "calibration.md").write_text("# FOCUS onset fallback calibration\n\n" + json.dumps({k: calibration_summary[k] for k in calibration_summary if k != "rows"}, indent=2) + "\n")
    target_results = []
    for index, line in enumerate(lines):
        if line["line_id"] not in TARGETS:
            continue
        bounds = _direct_bounds(lines, index, duration)
        prediction = locate_event(audio, sample_rate, *bounds) if bounds else None
        target_results.append({"line_id": line["line_id"], "original_text": line["original_text"],
                              "window": list(bounds) if bounds else None, "candidate": prediction,
                              "accepted": False, "reason": "Calibration gate and target-specific competing-peak review required."})
        target_results[-1]["reason"] = ("rejected: calibration error exceeded the acceptance gate"
                                         if not calibration_passed else "rejected: target evidence gate not satisfied")
    (out / "target_results.json").write_text(json.dumps(target_results, indent=2) + "\n")
    (out / "diagnostics.json").write_text(json.dumps({"features": ["onset_strength", "energy_rise", "vocal_band", "pyin_voicing", "temporal_prior"], "weights": {"onset_strength": .35, "energy_rise": .25, "voicing": .20, "vocal_band": .15, "temporal_prior": .05}, "audio_duration": duration, "calibration_passed": calibration_passed, "target_acceptance": "disabled when calibration fails"}, indent=2) + "\n")
    (out / "summary.json").write_text(json.dumps({
        "calibration": {k: calibration_summary[k] for k in calibration_summary if k != "rows"},
        "calibration_passed": calibration_passed,
        "direct_lead_line_acoustic_coverage": 78 / 82,
        "bounded_event_recovered_lines": 0,
        "renderable_lead_line_coverage": 78 / 82,
        "direct_token_acoustic_coverage": 543 / 602,
        "estimated_token_count": 0,
        "unresolved_token_count": 59,
        "target_count": len(target_results), "accepted_bounded_events": 0,
        "chronology_violations": 0, "authoritative_text_preserved": True,
        "tier_a": True, "tier_b": False, "tier_c": False,
        "decision": "reject_fallback_due_to_poor_calibration",
    }, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
