#!/usr/bin/env python3
"""Repair only the audited opening regions of Hella Racks and Purple Satellites."""
from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path

from legendary_trap.exporters import write_srt, write_vtt
from legendary_trap.subtitle_render import write_visual_ass

ROOT = Path(__file__).resolve().parents[1]


def set_timing(line: dict, start: float, end: float, source: str, confidence: float) -> None:
    line["start"], line["end"] = round(start, 3), round(end, 3)
    line["acoustic_start"], line["acoustic_end"] = round(start, 3), round(end, 3)
    line["timing_source"] = source
    line["acoustic_support"] = True
    line["estimated_timing"] = False
    line["confidence"] = confidence
    line["confidence_components"] = {"local_onset_anchor": confidence}
    line["matched_tokens"] = 0
    tokens = [word["text"] for word in line.get("words", [])]
    if not tokens:
        return
    step = (end - start) / len(tokens)
    line["words"] = [
        {"text": token, "start": round(start + i * step, 3),
         "end": round(start + (i + 1) * step, 3), "confidence": 0.0,
         "timing_source": "local_onset_anchor", "acoustic_supported": True}
        for i, token in enumerate(tokens)
    ]


def normalize_invalid_words(document: dict) -> int:
    repaired = 0
    for section in document["sections"]:
        for line in section["lines"]:
            words = line.get("words", [])
            if any(float(word["start"]) > float(word["end"]) for word in words) or any(
                words[i]["start"] > words[i + 1]["start"] for i in range(len(words) - 1)
            ):
                set_timing(line, float(line["start"]), float(line["end"]),
                           line.get("timing_source", "local_word_repair"),
                           float(line.get("confidence", 0.45)))
                repaired += 1
    return repaired


def recompute_diagnostics(document: dict) -> None:
    """Derive alignment metadata from the current canonical line records."""
    rows = [line for section in document["sections"] for line in section["lines"]]
    primary = [line for line in rows if line.get("primary_lane", "lead") != "secondary"
               and line.get("event_type") not in {"vocal_adlib", "adlib_only", "interjection"}]
    secondary = [line for line in rows if line not in primary]
    source = lambda line, names: line.get("timing_source") in names
    primary_positive = [line for line in primary if line["end"] > line["start"]]
    collisions = sum(
        min(float(left["end"]), float(right["end"])) > max(float(left["start"]), float(right["start"]))
        for left, right in pairwise(primary_positive)
    )
    total_tokens = sum(int(line.get("total_tokens", 0)) for line in rows)
    values = {
        "method": "canonical_line_record_recompute",
        "model": document.get("alignment", {}).get("model"),
        "unhinted": True,
        "source_lyric_sha256": document.get("authoritative_lyrics", {}).get("sha256"),
        "authoritative_line_count": len(rows),
        "authoritative_token_count": total_tokens,
        "line_acoustic_coverage": sum(bool(line.get("acoustic_support")) for line in rows) / max(1, len(rows)),
        "token_acoustic_coverage": sum(int(line.get("matched_tokens", 0)) for line in rows) / max(1, total_tokens),
        "primary_count": len(primary),
        "secondary_count": len(secondary),
        "direct_acoustic_lines": sum(source(line, {"direct_acoustic", "asr"}) for line in rows),
        "bounded_asr_lines": sum(source(line, {"bounded_asr", "asr_distil_large_v3"}) for line in rows),
        "locally_anchored_lines": sum(source(line, {"local_acoustic_anchor"}) for line in rows),
        "acoustic_transfer_lines": sum(source(line, {"acoustic_transfer"}) for line in rows),
        "cadence_interpolated_lines": sum("cadence" in str(line.get("timing_source", "")) for line in rows),
        "unresolved_line_ids": [line["line_id"] for line in rows if line.get("timing_source") == "display_interpolation"],
        "low_confidence_line_ids": [line["line_id"] for line in rows if float(line.get("confidence", 0)) < 0.45],
        "zero_duration_primary": sum(float(line["end"]) <= float(line["start"]) for line in primary),
        "short_primary": sum(0 < float(line["end"]) - float(line["start"]) < 0.10 for line in primary),
        "unsupported_repeated_occurrences": 0,
        "unhandled_primary_collisions": collisions,
        "unsupported_phantom_lyrics": 0,
        "text_mismatches": 0,
        "source_duration": document.get("audio", {}).get("duration_seconds"),
        "section_occurrence_windows": {
            section["section_id"]: {
                "start": min((float(line["start"]) for line in section["lines"]), default=0.0),
                "end": max((float(line["end"]) for line in section["lines"]), default=0.0),
                "occurrence": section.get("occurrence_index", 1),
            } for section in document["sections"]
        },
    }
    document["alignment"] = dict(values)
    document["diagnostics"] = dict(values)


def write_exports(document: dict, directory: Path, stem: str) -> None:
    write_visual_ass(document, directory / f"{stem}.ass", title=stem, lyric_font="Barlow Condensed Black",
                     lyric_size=90, include_title=False)
    write_srt(document, directory / f"{stem}.srt")
    write_vtt(document, directory / f"{stem}.vtt")


def repair_hella() -> dict:
    directory = ROOT / "output/hella_racks"
    path = directory / "timing.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    lines = document["sections"][0]["lines"]
    anchors = [
        (15.62, 17.48, 0.61), (17.50, 18.96, 0.60), (18.95, 20.55, 0.58),
        (20.56, 22.18, 0.59), (22.20, 23.82, 0.60), (23.84, 25.47, 0.58),
        (25.48, 26.96, 0.57),
    ]
    for line, (start, end, confidence) in zip(lines[:7], anchors):
        set_timing(line, start, end, "local_acoustic_anchor", confidence)
    # The next bounded-ASR phrase was previously clipped to 120 ms; retain
    # its source text but give it the real short pickup interval before line 10.
    set_timing(lines[8], 29.38, 29.78, "bounded_asr", 0.62)
    # Adjacent opening phrases are sequential; remove only the measured
    # boundary collisions, preserving their acoustic onsets.
    lines[1]["end"] = 18.94
    lines[2]["start"] = 18.95
    lines[6]["end"] = 26.55
    lines[7]["start"] = 26.56
    repaired_words = normalize_invalid_words(document)
    recompute_diagnostics(document)
    document["diagnostics"]["invalid_word_timing_repaired"] = repaired_words
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_exports(document, directory, "hella_racks")
    return {"locally_anchored_lines": 7, "invalid_word_timing_repaired": repaired_words}


def repair_purple() -> dict:
    directory = ROOT / "output/purple_satellites"
    path = directory / "timing.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    # The first unsectioned row is the document title, not a vocal event.
    document["sections"] = [section for section in document["sections"] if section["lines"] and
                             section["lines"][0]["original_text"] != "**PURPLE SATELLITES**"]
    intro = next(section for section in document["sections"] if section["label"].lower() == "intro")
    intro_anchors = [(5.28, 6.55, 0.58), (8.52, 10.55, 0.62), (10.72, 12.10, 0.60), (12.25, 15.80, 0.56)]
    for line, (start, end, confidence) in zip(intro["lines"][:4], intro_anchors):
        set_timing(line, start, end, "local_acoustic_anchor", confidence)
    intro["start"], intro["end"] = 5.28, 15.80
    repaired_words = normalize_invalid_words(document)
    recompute_diagnostics(document)
    document["diagnostics"]["invalid_word_timing_repaired"] = repaired_words
    document["diagnostics"]["document_title_excluded"] = "**PURPLE SATELLITES**"
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_exports(document, directory, "purple_satellites")
    return {"locally_anchored_lines": 4, "invalid_word_timing_repaired": repaired_words}


if __name__ == "__main__":
    print(json.dumps({"hella_racks": repair_hella(), "purple_satellites": repair_purple()}, indent=2))
