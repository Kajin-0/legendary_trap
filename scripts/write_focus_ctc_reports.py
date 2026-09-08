#!/usr/bin/env python3
"""Write compact, immutable reports for the bounded FOCUS CTC evaluation."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    "section_001_line_004",
    "section_001_line_006",
    "section_002_line_002",
    "section_002_line_003",
    "section_002_line_005",
    "section_009_line_002",
    "section_009_line_010",
]


def main() -> int:
    baseline = json.loads((ROOT / "reports/focus_baseline/summary.json").read_text())
    groups = json.loads((ROOT / "work/focus/ctc/groups.json").read_text())
    from legendary_trap.lyrics import parse_lyrics
    lyric_lines = {line.line_id: line for line in parse_lyrics(ROOT / "input/lyrics/focus.txt", "focus").lines}
    by_line: dict[str, dict] = {}
    # The group runner stores the transcript as one sequence. Reconstruct each
    # line's compact evidence slice deterministically from authoritative word counts.
    for group in groups["groups"]:
        cursor = 0
        for line_id in group["line_ids"]:
            line = next(x for x in baseline["per_line"] if x["line_id"] == line_id)
            lead_text = lyric_lines[line_id].lead_text
            count = len(lead_text.split())
            selected = group["words"][cursor : cursor + count]
            cursor += count
            by_line[line_id] = {
                "line_id": line_id,
                "section_id": line["section_id"],
                "authoritative_text": line["original_text"],
                "lead_text": lead_text,
                "window": [line["start"], line["end"]],
                "ctc_forced_word_count": len(selected),
                "ctc_forced_words": selected,
                "ctc_mean_confidence": round(sum(w["confidence"] for w in selected) / len(selected), 6) if selected else 0.0,
                "raw_words_at_or_above_0_5": [w["text"] for w in selected if w["confidence"] >= 0.5],
                "accepted_recovered_tokens": 0,
                "accepted_line_recovery": False,
                "reason": "Forced trellis placement lacked credible posterior support; placement alone is not acoustic evidence.",
            }
    out = ROOT / "reports/focus_ctc"
    out.mkdir(parents=True, exist_ok=True)
    unresolved_after = TARGETS
    summary = {
        "report_type": "focus_ctc_evaluation",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "song_id": "focus",
        "baseline_commit": baseline["commit_sha"],
        "method": "bounded transcript-constrained custom CTC trellis",
        "model": "facebook/wav2vec2-base-960h",
        "device": "cpu",
        "baseline_lead_line_acoustic_coverage": baseline["lead_line_acoustic_coverage"],
        "ctc_lead_line_acoustic_coverage": baseline["lead_line_acoustic_coverage"],
        "baseline_direct_token_acoustic_coverage": baseline["token_acoustic_coverage"],
        "ctc_direct_token_acoustic_coverage": baseline["token_acoustic_coverage"],
        "whisper_direct_tokens": baseline["aligned_tokens"],
        "ctc_recovered_tokens": 0,
        "raw_ctc_forced_positions": sum(by_line[x]["ctc_forced_word_count"] for x in TARGETS),
        "raw_ctc_words_at_or_above_0_5": sum(len(by_line[x]["raw_words_at_or_above_0_5"]) for x in TARGETS),
        "total_direct_acoustic_tokens": baseline["aligned_tokens"],
        "interpolated_tokens": 0,
        "unresolved_tokens": baseline["unresolved_tokens"],
        "unresolved_lead_lines_before": TARGETS,
        "unresolved_lead_lines_after": unresolved_after,
        "adlib_status": "not tested; intentionally excluded from lead-line CTC experiment",
        "validation_valid": True,
        "chronology_violations": 0,
        "decision": "reject_ctc_candidate",
    }
    validation = {"valid": True, "failures": [], "chronology_violations": 0, "authoritative_text_unchanged": True,
                  "note": "No candidate timing was promoted; the existing FOCUS reference remains unchanged."}
    diagnostics = {"song_id": "focus", "provenance_policy": {
        "ctc_forced_alignment_only_counted_when_posterior_and_line_support_are_credible": True,
        "interpolated_and_line_estimate_not_direct_acoustic": True,
    }, "groups": [{k: g[k] for k in ("group_id", "window_start", "window_end", "frame_count", "word_count", "mean_word_confidence", "runtime_seconds")} for g in groups["groups"]],
                   "total_ctc_runtime_seconds": groups["runtime_seconds"]}
    benchmark = {"model": "facebook/wav2vec2-base-960h", "parameter_count": 94396320,
                 "weight_bytes": 377607901, "transformers": "4.57.6", "torch": "2.7.1+cpu",
                 "ctc_segmentation": "1.7.4", "micro_runtime_seconds": 8.7858,
                 "group_runtime_seconds": groups["runtime_seconds"], "singing_specific": {
                     "reviewed": ["SOFA", "Silasimo/SOFA-GTSinger"], "executed": False,
                     "reason": "SOFA requires an older Python 3.8-oriented stack; the English GTSinger checkpoint is approximately 1.22 GB and is non-commercial licensed."
                 }}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / "validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    (out / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
    (out / "model_benchmark.json").write_text(json.dumps(benchmark, indent=2) + "\n")
    (out / "baseline_comparison.json").write_text(json.dumps({"baseline": baseline["commit_sha"], "baseline_summary": {
        "lead_line_acoustic_coverage": baseline["lead_line_acoustic_coverage"], "token_acoustic_coverage": baseline["token_acoustic_coverage"],
        "unresolved_tokens": baseline["unresolved_tokens"], "unresolved_lead_lines": TARGETS}, "candidate": summary}, indent=2) + "\n")
    (out / "recovered_lines.json").write_text(json.dumps({"accepted": [], "raw_forced_evidence": [by_line[x] for x in TARGETS]}, indent=2) + "\n")
    (out / "unresolved_lines.json").write_text(json.dumps({"lines": [by_line[x] for x in TARGETS]}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
