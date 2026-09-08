#!/usr/bin/env python3
"""Create compact reports for the bounded FOCUS singing-aligner evaluation."""
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
GROUP_LINES = {
    "intro": ["section_001_line_003", "section_001_line_004", "section_001_line_005", "section_001_line_006"],
    "early_section": ["section_002_line_001", "section_002_line_002", "section_002_line_003", "section_002_line_004", "section_002_line_005"],
    "outro": ["section_009_line_002", "section_009_line_003", "section_009_line_005", "section_009_line_007", "section_009_line_008", "section_009_line_010"],
}


def main() -> int:
    baseline = json.loads((ROOT / "reports/focus_baseline/summary.json").read_text())
    baseline_by_id = {x["line_id"]: x for x in baseline["per_line"]}
    groups = json.loads((ROOT / "work/focus/singing_aligner/groups.json").read_text())
    all_lines = {}
    for group in groups["groups"]:
        cursor = 0
        for line_id in GROUP_LINES[group["group_id"]]:
            count = baseline_by_id[line_id]["total_tokens"]
            words = group["words"][cursor:cursor + count]
            cursor += count
            supported = sum(w["acoustic_support"] for w in words)
            all_lines[line_id] = {
                "line_id": line_id,
                "section_id": baseline_by_id[line_id]["section_id"],
                "authoritative_text": baseline_by_id[line_id]["original_text"],
                "window": [baseline_by_id[line_id]["start"], baseline_by_id[line_id]["end"]],
                "word_count": len(words),
                "supported_words": supported,
                "phoneme_support": words,
                "line_acoustic_support": False,
                "reason": "No credible singing-aligner word evidence; forced placement is retained only as diagnostic output.",
            }
    out = ROOT / "reports/focus_singing_aligner"
    out.mkdir(parents=True, exist_ok=True)
    recovered = []
    unresolved = [all_lines[x] for x in TARGETS]
    summary = {
        "report_type": "focus_singing_specific_forced_alignment",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "song_id": "focus",
        "upstream_commit": "72be8a14b9126c201e0b8920513764c44ccd3f9",
        "model": "schufo/lyrics-aligner model_parameters.pth",
        "device": "cpu",
        "baseline_lead_line_acoustic_coverage": baseline["lead_line_acoustic_coverage"],
        "final_lead_line_acoustic_coverage": baseline["lead_line_acoustic_coverage"],
        "baseline_direct_token_acoustic_coverage": baseline["token_acoustic_coverage"],
        "final_direct_token_acoustic_coverage": baseline["token_acoustic_coverage"],
        "baseline_whisper_tokens": baseline["aligned_tokens"],
        "singing_aligner_recovered_tokens": 0,
        "total_direct_acoustic_tokens": baseline["aligned_tokens"],
        "unresolved_tokens": baseline["unresolved_tokens"],
        "baseline_lead_lines": 75,
        "singing_aligner_recovered_lead_lines": 0,
        "final_resolved_lead_lines": 75,
        "phoneme_acoustic_coverage": sum(x["supported_phonemes"] for x in groups["groups"]) / sum(x["phoneme_count"] for x in groups["groups"]),
        "target_line_phoneme_support": sum(sum(w["supported_phonemes"] for w in all_lines[x]["phoneme_support"]) for x in TARGETS),
        "target_line_phonemes": sum(sum(w["phoneme_count"] for w in all_lines[x]["phoneme_support"]) for x in TARGETS),
        "unresolved_lead_lines_before": TARGETS,
        "unresolved_lead_lines_after": TARGETS,
        "adlib_status": "not tested; excluded by design",
        "validation_valid": True,
        "chronology_violations": 0,
        "decision": "reject_candidate",
        "tier_b": False,
    }
    environment = {
        "upstream_repository": "https://github.com/schufo/lyrics-aligner",
        "upstream_commit": summary["upstream_commit"],
        "compatibility": "modern project .venv; Python 3.13.7; PyTorch 2.7.1+cpu; isolated local return_complex=False patch",
        "legacy_environment_required": False,
        "legacy_environment_attempted": False,
        "model_checkpoint_bytes": 40357640,
        "model_checkpoint_size": "approximately 38.5 MiB",
        "cmudict": "1.1.3",
        "g2p_en": "2.1.0",
        "numpy": "2.5.3",
        "librosa": "1.0.0",
        "soundfile": "0.14.0",
        "torch": "2.7.1+cpu",
        "ffmpeg": "tools/ffmpeg-7.0.2-amd64-static/ffmpeg",
        "model_download_or_clone_runtime_seconds": 1.5,
        "license_conclusion": "MIT code; no explicit separate checkpoint restriction found; commercial redistribution remains subject to provenance review",
        "execution_control": "No command reached its wall-clock timeout. One duplicate expanded group process was explicitly terminated after inspection; the final three-group run completed in 186.71 seconds under timeout 5m.",
    }
    micro = json.loads((ROOT / "work/focus/singing_aligner/micro.json").read_text())
    benchmark = {
        "window": [micro["window_start"], micro["window_end"]],
        "transcript": "four lead-line context group containing section_002_line_002; ad-libs excluded",
        "model_runtime_seconds": micro["model_runtime_seconds"],
        "phoneme_count": micro["phoneme_count"],
        "supported_phonemes": micro["supported_phonemes"],
        "phoneme_acoustic_coverage": micro["phoneme_acoustic_coverage"],
        "target_line_meaningful_support": False,
        "oov_words": micro["g2p"]["oov_words"],
    }
    diagnostics = {
        "total_group_runtime_seconds": groups["runtime_seconds"],
        "groups": [{k: x[k] for k in ("group_id", "window_start", "window_end", "phoneme_count", "supported_phonemes", "phoneme_acoustic_coverage", "model_runtime_seconds", "vocal_magnitude_median", "vocal_magnitude_p95")} for x in groups["groups"]],
        "evidence_rule": "word is direct only when mean phoneme support >= 0.5; line recovery requires credible word support; forced placements alone never count",
        "target_lines": [{"line_id": x, "supported_words": all_lines[x]["supported_words"], "word_count": all_lines[x]["word_count"]} for x in TARGETS],
    }
    (out / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    (out / "micro_benchmark.json").write_text(json.dumps(benchmark, indent=2) + "\n")
    (out / "group_results.json").write_text(json.dumps(groups, indent=2) + "\n")
    (out / "recovered_lines.json").write_text(json.dumps({"lines": recovered}, indent=2) + "\n")
    (out / "unresolved_lines.json").write_text(json.dumps({"lines": unresolved}, indent=2) + "\n")
    (out / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / "README.md").write_text("""# FOCUS singing-specific alignment evaluation\n\nThe isolated `schufo/lyrics-aligner` checkpoint was loaded successfully by modern PyTorch 2.7 CPU after a local compatibility patch to the upstream STFT call. CMUdict plus g2p-en generated the ARPAbet alignment view; authoritative lyric text was not changed.\n\nThe model produced monotonic placements, but evidence was weak: only 5 of 258 group phonemes met the diagnostic support threshold, no target word met the direct evidence gate, and none of the seven unresolved lead lines was recovered. The candidate is therefore rejected and `reports/focus_final/` remains unchanged.\n\nAd-libs were excluded. No candidate timing/subtitle files were generated.\n""")
    (out / "license_review.md").write_text((ROOT / "reports/focus_singing_aligner/license_review.md").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
