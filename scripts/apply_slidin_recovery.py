#!/usr/bin/env python3
"""Fuse accepted bounded distil-large-v3 evidence into slidin timing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from legendary_trap.validation import validate

ROOT = Path(__file__).resolve().parents[1]


def accepted(row: dict) -> bool:
    if not row["total_tokens"]:
        return False
    probabilities = [word["probability"] for word in row["words"]]
    coverage = row["matched_tokens"] / row["total_tokens"]
    strong_ratio = sum(value >= 0.5 for value in probabilities) / max(1, len(probabilities))
    # The line product does not require every internal word to survive ASR,
    # but it does require a substantial, high-probability lexical occurrence.
    return coverage >= 0.60 and row["probability_mean"] >= 0.75 and strong_ratio >= 0.75


def estimate_residual_groups(document: dict, residual_ids: set[str]) -> None:
    """Interpolate consecutive residual lines once between reliable anchors."""
    flat = [line for section in document["sections"] for line in section["lines"]]
    index_by_id = {line["line_id"]: index for index, line in enumerate(flat)}
    residual_indices = sorted(index_by_id[line_id] for line_id in residual_ids)
    groups: list[list[int]] = []
    for index in residual_indices:
        if not groups or index != groups[-1][-1] + 1:
            groups.append([index])
        else:
            groups[-1].append(index)
    for group in groups:
        left = 0.0
        for index in range(group[0] - 1, -1, -1):
            if flat[index]["line_id"] not in residual_ids and flat[index]["end"] > flat[index]["start"]:
                left = float(flat[index]["end"])
                break
        right = float(document["audio"]["duration_seconds"])
        for index in range(group[-1] + 1, len(flat)):
            if flat[index]["line_id"] not in residual_ids and flat[index]["end"] > flat[index]["start"]:
                right = float(flat[index]["start"])
                break
        right = max(left, right)
        weights = [max(1.0, float(line.get("total_tokens", 0))) for line in (flat[index] for index in group)]
        scale = (right - left) / sum(weights) if sum(weights) else 0.0
        cursor = left
        for index, weight in zip(group, weights):
            line = flat[index]
            end = min(right, cursor + weight * scale)
            line["start"], line["end"] = round(cursor, 3), round(end, 3)
            line["acoustic_start"], line["acoustic_end"] = None, None
            line["timing_source"], line["estimated_timing"] = "estimated", True
            line["acoustic_supported"], line["confidence"] = False, 0.0
            line["confidence_components"] = {"estimated": 1.0}
            for word_index, word in enumerate(line.get("words", [])):
                span = (end - cursor) / len(line["words"])
                word["start"] = round(cursor + word_index * span, 3)
                word["end"] = round(cursor + (word_index + 1) * span, 3)
                word["confidence"] = 0.0
                word["timing_source"] = "line_estimate"
                word["acoustic_supported"] = False
            cursor = end


def enforce_start_chronology(document: dict) -> None:
    """Keep a residual estimate from crossing a later trusted event."""
    previous = 0.0
    previous_end = 0.0
    for section in document["sections"]:
        for line in section["lines"]:
            if line["start"] < previous_end - 0.01 and line.get("timing_source") == "estimated":
                line["start"] = round(previous_end, 3)
                line["end"] = round(max(line["end"], line["start"]), 3)
                line["chronology_adjusted"] = True
            if line["start"] < previous - 0.01:
                line["start"] = round(previous, 3)
                line["end"] = round(max(line["end"], line["start"]), 3)
                line["chronology_adjusted"] = True
            previous = line["start"]
            previous_end = max(previous_end, line["end"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("song_id", choices=("slidin", "you_missed_it", "we_got_chemistry", "off_the_wave", "commin_long_ways", "chokehold"))
    args = parser.parse_args()
    song_id = args.song_id
    timing_path = ROOT / "output" / song_id / "timing.json"
    document = json.loads(timing_path.read_text())
    recovery = json.loads((ROOT / "work" / song_id / "large_whisper/groups.json").read_text())
    by_id = {}
    for group in recovery["groups"]:
        for row in group["lines"]:
            if accepted(row):
                current = by_id.get(row["line_id"])
                score = row["matched_tokens"] / max(1, row["total_tokens"]) * row["probability_mean"]
                if current is None or score > current[0]:
                    by_id[row["line_id"]] = (score, row)

    # Reject a bounded result when it crosses a trusted direct line outside
    # its local candidate chain. This prevents a good-sounding phrase from
    # being attached to a repeated occurrence in the wrong section.
    flat_before = [line for section in document["sections"] for line in section["lines"]]
    candidate_ids = set(by_id)
    filtered = {}
    for index, line in enumerate(flat_before):
        candidate = by_id.get(line["line_id"])
        if candidate is None:
            continue
        previous_anchor = next((flat_before[position] for position in range(index - 1, -1, -1)
                                if flat_before[position]["line_id"] not in candidate_ids
                                and flat_before[position].get("matched_tokens", 0) > 0), None)
        next_anchor = next((flat_before[position] for position in range(index + 1, len(flat_before))
                            if flat_before[position]["line_id"] not in candidate_ids
                            and flat_before[position].get("matched_tokens", 0) > 0), None)
        row = candidate[1]
        if previous_anchor and row["start"] < previous_anchor["end"] - 0.01:
            continue
        if next_anchor and row["end"] > next_anchor["start"] + 0.01:
            continue
        filtered[line["line_id"]] = candidate
    by_id = filtered

    applied = []
    for section in document["sections"]:
        for line in section["lines"]:
            row = by_id.get(line["line_id"])
            if row is None or (line.get("matched_tokens", 0) and line.get("confidence", 0.0) >= 0.75):
                continue
            _, row = row
            line["start"], line["end"] = row["start"], row["end"]
            line["acoustic_start"], line["acoustic_end"] = row["start"], row["end"]
            line["matched_tokens"] = row["matched_tokens"]
            line["confidence"] = round(min(0.99, 0.50 * row["coverage"] +
                                            0.30 * row["probability_mean"] + 0.20), 4)
            line["confidence_components"] = {
                "token_coverage": row["coverage"],
                "acoustic_support": row["probability_mean"],
                "temporal_consistency": 1.0,
                "bounded_asr": 1.0,
            }
            line["timing_source"], line["estimated_timing"] = "asr_distil_large_v3", False
            line["acoustic_supported"] = True
            line["words"] = row["words"]
            applied.append({"line_id": line["line_id"], "matched_tokens": row["matched_tokens"],
                            "total_tokens": row["total_tokens"], "start": row["start"], "end": row["end"],
                            "probability_mean": row["probability_mean"]})

    residual_ids = {line["line_id"] for section in document["sections"] for line in section["lines"]
                    if line.get("matched_tokens", 0) == 0}
    for section in document["sections"]:
        for line in section["lines"]:
            if line["line_id"] in residual_ids:
                line["start"], line["end"] = 0.0, 0.0
    estimate_residual_groups(document, residual_ids)
    for section in document["sections"]:
        for line in section["lines"]:
            if line["end"] <= line["start"]:
                line["end"] = round(min(float(document["audio"]["duration_seconds"]), line["start"] + 0.05), 3)
    enforce_start_chronology(document)
    duration = float(document["audio"]["duration_seconds"])
    manifest = json.loads((ROOT / "song_manifest.json").read_text())
    song = next(item for item in manifest["songs"] if item["id"] == song_id)
    validation = validate(document, ROOT / song["lyrics_path"], song["lyrics_sha256"], duration)
    final_path = ROOT / "output" / song_id / "render_timing.json"
    final_path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    timing_path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    rows = [line for section in document["sections"] for line in section["lines"]]
    lead = [line for line in rows if line.get("total_tokens", 0) > 0]
    direct_line = lambda line: bool(line.get("acoustic_supported", False)) or (
        line.get("matched_tokens", 0) > 0 and line.get("timing_source") != "estimated")
    report = {
        "song_id": song_id, "model": recovery["model"], "applied_rows": applied,
        "recovered_line_count": len(applied), "estimated_line_ids": [line["line_id"] for line in rows
            if line.get("timing_source") == "estimated"],
        "estimated_line_count": sum(line.get("timing_source") == "estimated" for line in rows),
        "direct_lead_line_count": sum(direct_line(line) for line in lead),
        "lead_line_count": len(lead),
        "direct_lead_line_coverage": sum(direct_line(line) for line in lead) / len(lead),
        "direct_token_count": sum(line.get("matched_tokens", 0) for line in lead),
        "authoritative_token_count": sum(line.get("total_tokens", 0) for line in lead),
        "direct_token_coverage": sum(line.get("matched_tokens", 0) for line in lead) /
                                 max(1, sum(line.get("total_tokens", 0) for line in lead)),
        "chronology_violations": 0, "validation": validation,
    }
    out = ROOT / "reports" / f"{song_id}_alignment"
    (out / "high_capacity_recovery.json").write_text(json.dumps({"recovery": recovery, "accepted": applied}, indent=2) + "\n")
    (out / "final_summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if validation["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
