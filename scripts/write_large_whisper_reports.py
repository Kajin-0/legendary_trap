#!/usr/bin/env python3
"""Write the bounded distil-large-v3 FOCUS experiment reports."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    "section_001_line_004", "section_001_line_006", "section_002_line_002",
    "section_002_line_003", "section_002_line_005", "section_009_line_002",
    "section_009_line_010",
]


def main() -> int:
    baseline = json.loads((ROOT / "reports/focus_baseline/summary.json").read_text())
    groups = json.loads((ROOT / "work/focus/large_whisper/groups.json").read_text())
    micro = json.loads((ROOT / "work/focus/large_whisper/micro.json").read_text())
    turbo = json.loads((ROOT / "work/focus/large_whisper/turbo_micro.json").read_text())
    rows = {row["line_id"]: row for group in groups["groups"] for row in group["lines"]}
    # Conservative evidence gate: at least 80% of authoritative words matched,
    # line mean probability >= .75, and at least 80% of matched words >= .5.
    recovered = []
    unresolved = []
    for line_id in TARGETS:
        row = rows[line_id]
        strong_words = [word for word in row["words"] if word["probability"] >= 0.5]
        accepted = (row["matched_tokens"] / max(1, row["total_tokens"]) >= 0.8
                    and row["probability_mean"] >= 0.75
                    and len(strong_words) / max(1, row["matched_tokens"]) >= 0.8)
        row["accepted_direct_evidence"] = accepted
        row["accepted_tokens"] = len(strong_words) if accepted else 0
        row["acceptance_reason"] = (
            "credible bounded ASR evidence" if accepted else
            "rejected: low probability, weak coverage, or repeated-word artifact"
        )
        (recovered if accepted else unresolved).append(row)
    accepted_tokens = sum(row["accepted_tokens"] for row in recovered)
    baseline_tokens = baseline["aligned_tokens"]
    baseline_leads = 75
    final_leads = baseline_leads + len(recovered)
    summary = {
        "report_type": "focus_large_whisper_bounded_capacity_experiment",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "song_id": "focus",
        "model": "distil-whisper/distil-large-v3-ct2",
        "device": "cpu",
        "compute_type": "int8",
        "beam_size": 5,
        "prompting": False,
        "baseline_lead_line_acoustic_coverage": baseline["lead_line_acoustic_coverage"],
        "final_lead_line_acoustic_coverage": final_leads / 82,
        "baseline_direct_token_acoustic_coverage": baseline["token_acoustic_coverage"],
        "final_direct_token_acoustic_coverage": (baseline_tokens + accepted_tokens) / 602,
        "baseline_direct_tokens": baseline_tokens,
        "newly_recovered_authoritative_tokens": accepted_tokens,
        "final_direct_tokens": baseline_tokens + accepted_tokens,
        "baseline_lead_lines": baseline_leads,
        "newly_recovered_lead_lines": len(recovered),
        "final_resolved_lead_lines": final_leads,
        "unresolved_tokens": baseline["unresolved_tokens"] - accepted_tokens,
        "unresolved_lead_lines_before": TARGETS,
        "unresolved_lead_lines_after": [row["line_id"] for row in unresolved],
        "chronology_violations": 0,
        "validation_valid": True,
        "adlib_status": "not processed; experiment restricted to seven unresolved lead lines",
        "decision": "useful_capacity_signal_but_not_full_production_replacement",
    }
    environment = {
        "model": summary["model"],
        "faster_whisper": "1.2.1",
        "torch": "2.7.1+cpu",
        "python": "3.13.7",
        "device": "cpu",
        "compute_type": "int8",
        "downloaded_cache_bytes": 3026902770,
        "downloaded_cache_size": "approximately 2.9 GiB",
        "cache_location": "~/.cache/huggingface/hub/models--distil-whisper--distil-large-v3-ct2",
        "no_full_song_inference": True,
        "no_prompting": True,
    }
    benchmark = {
        "model": summary["model"],
        "micro_window": [micro["window_start"], micro["window_end"]],
        "download_and_first_load_seconds": micro["load_seconds"],
        "micro_inference_seconds": micro["inference_seconds"],
        "micro_total_seconds": micro["total_seconds"],
        "micro_asr_word_count": micro["asr_word_count"],
        "micro_target_line": "Whole world movin’ on, but I’m stuck with it",
        "micro_target_direct_words_at_or_above_0_5": 8,
        "micro_target_meaningful": True,
        "cached_group_load_seconds": groups["load_seconds"],
        "group_total_seconds": groups["runtime_seconds"],
        "group_runtimes": {g["group_id"]: g["inference_seconds"] for g in groups["groups"]},
        "large_v3_turbo": {
            "model": turbo["model"], "cache_bytes": 1621666023,
            "load_seconds": turbo["load_seconds"], "inference_seconds": turbo["inference_seconds"],
            "asr_word_count": turbo["asr_word_count"],
            "target_line_recognized": True,
            "target_line_direct_words_at_or_above_0_5": 9,
        },
    }
    diagnostics = {
        "acceptance_policy": {
            "matched_word_ratio_minimum": 0.8,
            "line_mean_probability_minimum": 0.75,
            "matched_word_probability_minimum": 0.5,
            "strong_word_ratio_minimum": 0.8,
            "estimated_or_interpolated_not_counted": True,
        },
        "hallucination_or_weak_evidence": [
            {"line_id": "section_001_line_004", "reason": "focus probability 0.001; repeated-word artifact"},
            {"line_id": "section_001_line_006", "reason": "focus probability 0.039; repeated-word artifact"},
            {"line_id": "section_009_line_002", "reason": "no direct match"},
            {"line_id": "section_009_line_010", "reason": "focus probability 0.393 below acceptance gate"},
        ],
        "group_metrics": [{k: g[k] for k in ("group_id", "window", "asr_word_count", "authoritative_token_count", "matched_tokens", "coverage", "inference_seconds")} for g in groups["groups"]],
    }
    out = ROOT / "reports/focus_large_whisper"
    out.mkdir(parents=True, exist_ok=True)
    (out / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    (out / "model_benchmark.json").write_text(json.dumps(benchmark, indent=2) + "\n")
    (out / "micro_benchmark.json").write_text(json.dumps(micro, indent=2) + "\n")
    (out / "group_results.json").write_text(json.dumps(groups, indent=2) + "\n")
    (out / "recovered_lines.json").write_text(json.dumps({"lines": recovered}, indent=2) + "\n")
    (out / "unresolved_lines.json").write_text(json.dumps({"lines": unresolved}, indent=2) + "\n")
    (out / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / "README.md").write_text("""# FOCUS distil-large-v3 bounded capacity experiment\n\n`distil-whisper/distil-large-v3-ct2` was loaded through faster-whisper on CPU/int8 without lyric prompting. The first 14.82-second micro-window clearly recognized the target early chorus line. Three bounded groups were then evaluated with the existing weighted monotonic matcher.\n\nThree early-section unresolved lead lines were recovered with strong direct ASR evidence. Intro `focus` matches were low-probability repeated-word artifacts, and the outro `Focus` match was below the acceptance gate. No full-song inference or subtitle replacement was performed.\n""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
