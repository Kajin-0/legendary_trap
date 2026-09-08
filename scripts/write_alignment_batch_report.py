#!/usr/bin/env python3
"""Write compact final reports for the six sequential alignment passes."""
from __future__ import annotations

import json
from pathlib import Path

from legendary_trap.validation import validate

ROOT = Path(__file__).resolve().parents[1]
SONGS = ["slidin", "you_missed_it", "we_got_chemistry", "off_the_wave",
         "commin_long_ways", "chokehold"]


def main() -> int:
    manifest = json.loads((ROOT / "song_manifest.json").read_text())
    by_id = {song["id"]: song for song in manifest["songs"]}
    reports = []
    for song_id in SONGS:
        song = by_id[song_id]
        output = ROOT / "output" / song_id
        document = json.loads((output / "render_timing.json").read_text())
        rows = [line for section in document["sections"] for line in section["lines"]]
        lead = [line for line in rows if line.get("total_tokens", 0) > 0]
        direct = [line for line in lead if line.get("timing_source") != "estimated"
                  and line.get("matched_tokens", 0) > 0]
        estimated = [line for line in rows if line.get("timing_source") == "estimated"]
        validation = validate(document, ROOT / song["lyrics_path"], song["lyrics_sha256"],
                              float(document["audio"]["duration_seconds"]))
        diagnostics = json.loads((output / f"{song_id}.render_diagnostics.json").read_text())
        alignment = ROOT / "reports" / f"{song_id}_alignment"
        recovery_detail = json.loads((alignment / "high_capacity_recovery.json").read_text())
        baseline = json.loads((alignment / "baseline_render_diagnostics.json").read_text())
        report = {
            "song_id": song_id,
            "old_estimated_lines": len(baseline.get("estimated_line_ids", [])),
            "new_estimated_lines": len(estimated),
            "estimated_line_ids": [line["line_id"] for line in estimated],
            "authoritative_lead_lines": len(lead),
            "direct_lead_lines": len(direct),
            "direct_lead_line_coverage": len(direct) / len(lead) if lead else 1.0,
            "direct_tokens": sum(line.get("matched_tokens", 0) for line in direct),
            "authoritative_tokens": sum(line.get("total_tokens", 0) for line in lead),
            "direct_token_coverage": sum(line.get("matched_tokens", 0) for line in direct) /
                                     max(1, sum(line.get("total_tokens", 0) for line in lead)),
            "high_capacity_recovered_lines": len(recovery_detail.get("accepted", [])),
            "high_capacity_applied_line_ids": [row["line_id"] for row in recovery_detail.get("accepted", [])],
            "duration_seconds": document["audio"]["duration_seconds"],
            "render_runtime_seconds": diagnostics.get("render_runtime_seconds"),
            "validation": validation,
            "video": str((output / f"{song_id}.mp4").relative_to(ROOT)),
            "subtitles": [str((output / f"{song_id}.{ext}").relative_to(ROOT)) for ext in ("ass", "srt", "vtt")],
            "timing": str((output / "render_timing.json").relative_to(ROOT)),
        }
        (alignment / "final_summary.json").write_text(json.dumps(report, indent=2) + "\n")
        (alignment / "README.md").write_text(
            f"# {song_id} alignment pass\n\n"
            f"The previous interpolated render had {report['old_estimated_lines']} estimated lines. "
            f"The established base.en monotonic alignment was followed by bounded, unprompted "
            f"distil-large-v3 recovery on weak windows. The renderable candidate has "
            f"{report['new_estimated_lines']} estimated lines and "
            f"{report['direct_lead_lines']}/{report['authoritative_lead_lines']} direct lead-line timing.\n\n"
            f"Validation: {'PASS' if validation['valid'] else 'FAIL'}. Remaining estimates are explicit "
            f"and were not counted as acoustic evidence.\n"
        )
        reports.append(report)
    summary = {"songs": reports, "all_valid": all(report["validation"]["valid"] for report in reports)}
    (ROOT / "reports" / "alignment_batch_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"all_valid": summary["all_valid"], "songs": len(reports)}, indent=2))
    return 0 if summary["all_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
