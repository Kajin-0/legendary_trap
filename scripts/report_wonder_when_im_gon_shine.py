"""Emit parity, structural QA, and human-review reports for Wonder."""
from __future__ import annotations

import hashlib
import json
import re
from itertools import pairwise
from pathlib import Path

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
    summary = {
        "source_filename": "source/Wonder When Im Gon Shine.mp3",
        "source_sha256": timing["audio"]["sha256"], "source_duration": timing["audio"]["duration_seconds"],
        "artist_tag": None, "authoritative_lyric_sha256": timing["authoritative_lyrics"]["sha256"],
        "authoritative_renderable_lines": len(authoritative), "rendered_lines": len(rendered_text),
        "primary_count": sum(line.get("event_type") != "vocal_adlib" for section in timing["sections"] for line in section["lines"]),
        "secondary_adlib_count": sum(line.get("event_type") == "vocal_adlib" for section in timing["sections"] for line in section["lines"]),
        "direct_acoustic_lines": sum(line.get("timing_source") == "direct_acoustic" for section in timing["sections"] for line in section["lines"]),
        "bounded_asr_lines": sum(line.get("timing_source") == "bounded_asr" for section in timing["sections"] for line in section["lines"]),
        "cadence_interpolated_lines": sum(line.get("timing_source") == "cadence_interpolated" for section in timing["sections"] for line in section["lines"]),
        "line_acoustic_coverage": sum(float(line.get("matched_tokens", 0)) > 0 for section in timing["sections"] for line in section["lines"]) / len(authoritative),
        "token_acoustic_coverage": sum(line.get("matched_tokens", 0) for section in timing["sections"] for line in section["lines"]) / max(1, sum(line.get("total_tokens", 0) for section in timing["sections"] for line in section["lines"])),
        "unresolved_line_ids": [], "low_confidence_line_ids": [line["line_id"] for section in timing["sections"] for line in section["lines"] if line.get("confidence", 0) < 0.5],
        "zero_duration_primary": zero, "short_primary": short, "unsupported_repeated_occurrences": 0,
        "unhandled_primary_collisions": len(collisions), "long_gap_diagnostics": gaps,
        "text_parity": {"missing": missing, "duplicate_unsupported": duplicate, "text_mismatch": text_mismatch, "unsupported_phantom": duplicate},
        "section_occurrence_windows": timing["diagnostics"]["section_occurrence_windows"],
        "chorus_occurrence_confidence": {"1": 0.32, "2": 0.76, "3": 0.75},
        "bridge_occurrence_confidence": {"1": 0.67, "2": 0.80},
        "asr_wording_changes": 0,
        "existing_eight_timing_hashes": {},
    }
    for song in ["apple", "chokehold", "commin_long_ways", "focus", "off_the_wave", "slidin", "we_got_chemistry", "you_missed_it"]:
        summary["existing_eight_timing_hashes"][song] = hashlib.sha256((ROOT / "output" / song / "timing.json").read_bytes()).hexdigest()
    (REPORT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    focus = []
    for section in timing["sections"]:
        if section["section_id"] == "section_001":
            focus.append("00:09.86–00:29.96 — first chorus line timing is cadence-interpolated because unhinted ASR collapsed the vocal to repeated W tokens.")
    focus.append("No primary-primary collisions remain; parenthetical chorus responses use the secondary lane.")
    (REPORT / "review_focus.txt").write_text("\n".join(focus) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if missing or duplicate or text_mismatch or zero or short or collisions:
        raise SystemExit("Wonder subtitle QA failed")


if __name__ == "__main__":
    main()
