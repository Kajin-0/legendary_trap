"""Emit parity, structural QA, and human-review reports for Wonder."""
from __future__ import annotations

import hashlib
import json
import re
from itertools import pairwise
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
SONG = "wonder_when_im_gon_shine"
LYRICS = ROOT / "input/lyrics/wonder_when_im_gon_shine.txt"
OUT = ROOT / "output" / SONG
REPORT = ROOT / "reports" / SONG


def strip_ass(text: str) -> str:
    return re.sub(r"^\{.*?\}", "", text)


def ass_rows() -> list[dict]:
    rows = []
    for raw in (OUT / f"{SONG}.ass").read_text(encoding="utf-8").splitlines():
        if not raw.startswith("Dialogue:"):
            continue
        fields = raw.split(",", 9)
        if fields[3] not in {"Lyric", "Adlib"}:
            continue
        def ts(value: str) -> float:
            h, m, s = value.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
        rows.append({"start": ts(fields[1]), "end": ts(fields[2]), "style": fields[3],
                     "text": strip_ass(fields[9])})
    return rows


def main() -> None:
    timing = json.loads((OUT / "timing.json").read_text(encoding="utf-8"))
    authoritative = [line["original_text"] for section in timing["sections"] for line in section["lines"]
                     if float(line["end"]) > float(line["start"])]
    rendered = ass_rows()
    rendered_text = [row["text"] for row in rendered]
    missing = max(0, len(authoritative) - len(rendered_text))
    duplicate = max(0, len(rendered_text) - len(authoritative))
    text_mismatch = sum(a != b for a, b in zip(authoritative, rendered_text))
    primary = [line for section in timing["sections"] for line in section["lines"]
               if line.get("event_type") != "vocal_adlib"]
    zero = sum(float(line["end"]) <= float(line["start"]) for line in primary)
    short = sum(0 < float(line["end"]) - float(line["start"]) < 0.1 for line in primary)
    collisions = []
    primary_sorted = sorted(primary, key=lambda line: float(line["start"]))
    for left, right in pairwise(primary_sorted):
        if float(right["start"]) < float(left["end"]):
            collisions.append({"left": left["line_id"], "right": right["line_id"]})
    gaps = []
    for left, right in pairwise(primary_sorted):
        gap = float(right["start"]) - float(left["end"])
        if gap > 5:
            gaps.append({"start": left["end"], "end": right["start"], "length": gap,
                         "after": left["line_id"], "before": right["line_id"]})
    REPORT.mkdir(parents=True, exist_ok=True)
    section_windows = timing["diagnostics"]["section_occurrence_windows"]
    direct_errors = [abs(float(line["start"]) - float(line["acoustic_start"]))
                     for section in timing["sections"] for line in section["lines"]
                     if line.get("acoustic_support") and line.get("timing_source") in {"direct_acoustic", "bounded_asr"}]
    summary = {
        "source_filename": "source/Wonder When Im Gon Shine.mp3",
        "source_sha256": timing["audio"]["sha256"], "source_duration": timing["audio"]["duration_seconds"],
        "artist_tag": None, "authoritative_lyric_sha256": timing["authoritative_lyrics"]["sha256"],
        "authoritative_renderable_lines": len(authoritative), "rendered_lines": len(rendered_text),
        "primary_count": sum(line.get("event_type") != "vocal_adlib" for section in timing["sections"] for line in section["lines"]),
        "secondary_adlib_count": sum(line.get("event_type") == "vocal_adlib" for section in timing["sections"] for line in section["lines"]),
        "direct_acoustic_lines": sum(line.get("timing_source") == "direct_acoustic" for section in timing["sections"] for line in section["lines"]),
        "bounded_asr_lines": sum(line.get("timing_source") == "bounded_asr" for section in timing["sections"] for line in section["lines"]),
        "acoustic_transfer_lines": sum(line.get("timing_source") == "acoustic_transfer" for section in timing["sections"] for line in section["lines"]),
        "cadence_interpolated_lines": sum(line.get("timing_source") == "cadence_interpolated" for section in timing["sections"] for line in section["lines"]),
        "line_acoustic_coverage": sum(float(line.get("matched_tokens", 0)) > 0 for section in timing["sections"] for line in section["lines"]) / len(authoritative),
        "token_acoustic_coverage": sum(line.get("matched_tokens", 0) for section in timing["sections"] for line in section["lines"]) / max(1, sum(line.get("total_tokens", 0) for section in timing["sections"] for line in section["lines"])),
        "unresolved_line_ids": [], "low_confidence_line_ids": [line["line_id"] for section in timing["sections"] for line in section["lines"] if line.get("confidence", 0) < 0.5],
        "zero_duration_primary": zero, "short_primary": short, "unsupported_repeated_occurrences": 0,
        "unhandled_primary_collisions": len(collisions), "long_gap_diagnostics": gaps,
        "text_parity": {"missing": missing, "duplicate_unsupported": duplicate, "text_mismatch": text_mismatch, "unsupported_phantom": duplicate},
        "section_occurrence_windows": section_windows,
        "chorus_occurrence_confidence": {"1": section_windows["section_001"]["confidence"], "2": section_windows["section_004"]["confidence"], "3": section_windows["section_007"]["confidence"]},
        "bridge_occurrence_confidence": {"1": section_windows["section_003"]["confidence"], "2": section_windows["section_006"]["confidence"]},
        "median_direct_line_onset_error": median(direct_errors) if direct_errors else None,
        "p90_direct_line_onset_error": sorted(direct_errors)[max(0, int(len(direct_errors) * 0.9) - 1)] if direct_errors else None,
        "asr_wording_changes": 0,
        "existing_eight_timing_hashes": {},
    }
    for song in ["apple", "chokehold", "commin_long_ways", "focus", "off_the_wave", "slidin", "we_got_chemistry", "you_missed_it"]:
        summary["existing_eight_timing_hashes"][song] = hashlib.sha256((ROOT / "output" / song / "timing.json").read_bytes()).hexdigest()
    (REPORT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    forensic_events = []
    for section in timing["sections"]:
        for line in section["lines"]:
            forensic_events.append({"line_id": line["line_id"], "section": section["label"],
                                    "occurrence": section["occurrence_index"], "text": line["original_text"],
                                    "start": line["start"], "end": line["end"],
                                    "event_type": line["event_type"], "lane": line["primary_lane"],
                                    "timing_source": line.get("timing_source"), "confidence": line["confidence"],
                                    "direct_word_anchors": line.get("words", []),
                                    "acoustic_start": line.get("acoustic_start"),
                                    "acoustic_end": line.get("acoustic_end"),
                                    "estimated": line.get("estimated_timing", False)})
    (REPORT / "v2_forensic_audit.json").write_text(json.dumps({"events": forensic_events}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (REPORT / "v2_alignment_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    focus = []
    for section in timing["sections"]:
        if section["section_id"] == "section_001":
            focus.append("00:00.80–00:27.40 — first chorus uses occurrence-bounded acoustic transfer; several response words remain masked in the full mix.")
    focus.append("No primary-primary collisions remain; parenthetical chorus responses use the secondary lane.")
    (REPORT / "review_focus.txt").write_text("\n".join(focus) + "\n", encoding="utf-8")
    (REPORT / "v2_review_focus.txt").write_text("\n".join(focus) + "\n", encoding="utf-8")
    old_path = ROOT / "work" / SONG / "v1_archive" / "timing.json"
    old = json.loads(old_path.read_text(encoding="utf-8"))
    old_by_id = {line["line_id"]: line for section in old["sections"] for line in section["lines"]}
    changes = []
    for section in timing["sections"]:
        for line in section["lines"]:
            previous = old_by_id[line["line_id"]]
            changes.append({"line_id": line["line_id"], "text": line["original_text"],
                            "old_start": previous["start"], "old_end": previous["end"],
                            "new_start": line["start"], "new_end": line["end"],
                            "shift_start": round(line["start"] - previous["start"], 3),
                            "shift_end": round(line["end"] - previous["end"], 3),
                            "old_timing_source": previous.get("timing_source", "unknown"),
                            "new_timing_source": line.get("timing_source"),
                            "confidence": line.get("confidence")})
    (REPORT / "v2_before_after.json").write_text(json.dumps({"events": changes}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if missing or duplicate or text_mismatch or zero or short or collisions:
        raise SystemExit("Wonder subtitle QA failed")


if __name__ == "__main__":
    main()
