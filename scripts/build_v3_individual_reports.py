"""Build auditable reports for the targeted FOCUS/chemistry recovery."""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/v3_individual_audit"


def lines(document: dict) -> list[dict]:
    return [line for section in document["sections"] for line in section["lines"]]


def focus_report() -> dict:
    current = json.loads((ROOT / "output/focus/timing.json").read_text())
    old = json.loads((ROOT / "reports/focus_final/timing.json").read_text())
    old_map = {line["line_id"]: line for line in lines(old)}
    section = next(s for s in current["sections"] if s["section_id"] == "section_002")
    rows = []
    for line in section["lines"]:
        old_line = old_map[line["line_id"]]
        rows.append({
            "line_id": line["line_id"], "text": line["original_text"],
            "old_start": old_line["start"], "old_end": old_line["end"],
            "new_start": line["start"], "new_end": line["end"],
            "shift_start": round(line["start"] - old_line["start"], 3),
            "shift_end": round(line["end"] - old_line["end"], 3),
            "timing_source": line.get("timing_source"),
            "confidence": line.get("confidence"),
            "direct_acoustic": bool(line.get("acoustic_supported")),
            "matched_tokens": line.get("matched_tokens", 0),
            "available_asr_anchor": line["line_id"] in {
                "section_002_line_001", "section_002_line_002", "section_002_line_003",
                "section_002_line_004", "section_002_line_005", "section_002_line_006",
                "section_002_line_007", "section_002_line_008",
            },
            "flags": {
                "old_zero_duration": old_line["end"] <= old_line["start"],
                "new_zero_duration": line["end"] <= line["start"],
                "estimated": line.get("estimated_timing", False),
            },
        })
    old_zero = sum(r["flags"]["old_zero_duration"] for r in rows)
    new_zero = sum(r["flags"]["new_zero_duration"] for r in rows)
    return {
        "song": "focus", "window": [0.0, 40.0],
        "source_hash": hashlib.sha256((ROOT / "source/FOCUS.mp3").read_bytes()).hexdigest(),
        "lyrics_hash": hashlib.sha256((ROOT / "input/lyrics/focus.txt").read_bytes()).hexdigest(),
        "evidence": ["work/focus/large_whisper/groups.json", "reports/focus_large_whisper/recovered_lines.json"],
        "first_chorus_occurrence_bound": [12.14, 34.50],
        "zero_duration_primary_before": old_zero,
        "zero_duration_primary_after": new_zero,
        "lines": rows,
        "chronology": all(rows[i]["new_end"] <= rows[i + 1]["new_start"]
                           for i in range(len(rows) - 1)),
    }


def chemistry_report() -> dict:
    timing = json.loads((ROOT / "output/we_got_chemistry/timing.json").read_text())
    asr = json.loads((OUT / "chemistry_late_asr.json").read_text())
    old_text = (ROOT / "reports/structural_alignment/we_got_chemistry_shadow.json").read_text()
    old_lines = json.loads((ROOT / "reports/final_sync_polish/we_got_chemistry.json").read_text())
    late_segments = [{"start": s["start"], "end": s["end"], "text": s["text"]}
                     for s in asr["segments"] if s["start"] >= 208.0]
    late_ids = {f"section_006_line_{index:03d}" for index in range(9, 14)}
    late_after = [{"line_id": line["line_id"], "text": line["original_text"],
                   "start": line["start"], "end": line["end"],
                   "timing_source": line.get("timing_source")}
                  for section in timing["sections"] for line in section["lines"]
                  if line["line_id"] in late_ids]
    return {
        "song": "we_got_chemistry", "window": [205.0, 249.24],
        "source_hash": hashlib.sha256((ROOT / "source/we got chemistry.mp3").read_bytes()).hexdigest(),
        "lyrics_hash_before": "84878ce78a520f176cd752b713ebfdc9c529b4f53d6f79d774ba08da20eda054",
        "lyrics_hash_after": timing["authoritative_lyrics"]["sha256"],
        "evidence": ["reports/v3_individual_audit/chemistry_late_asr.json",
                     "work/we_got_chemistry/large_whisper/groups.json",
                     "work/we_got_chemistry/asr-base.en.json"],
        "occurrence_conclusion": "one complete late hook; no second outro hook occurrence",
        "acoustic_occurrence_count": 1,
        "supported_audio": late_segments,
        "final_hook_text": [line["original_text"] for section in timing["sections"]
                             if section["section_id"] == "section_006" for line in section["lines"]],
        "outro_hook_text_before": [
            "We got chemistry", "Mixed with uncertainty", "Something about you keeps pulling me close",
            "Even when it’s hurting me", "Can’t deny the attraction", "Can’t ignore the reaction",
            "Every time you step inside the scene", "You become the distraction", "Yeah",
            "Thot on the weekend", "Heart got caught in the deep end", "Too many memories created",
            "From the moments we keep in",
        ],
        "outro_hook_text_after": [],
        "reference_decision": "B",
        "reference_diff": {"removed_block": "[outro hook] and its 13 lines", "wording_added": [],
                           "asr_wording_added": False},
        "timing_before": old_lines["lines_modified"],
        "timing_after": {"section_007_present": False, "last_supported_vocal_end": 232.12,
                         "late_lines": late_after},
        "cadence_guard": "repeat cadence cannot promote an occurrence without independent acoustic evidence",
        "old_shadow_excerpt_present": bool(old_text),
    }


def catalog_red_flags() -> dict:
    songs = ["apple", "chokehold", "commin_long_ways", "focus", "off_the_wave",
             "slidin", "we_got_chemistry", "you_missed_it"]
    result = []
    for song in songs:
        doc = json.loads((ROOT / "output" / song / "timing.json").read_text())
        duration = float(doc["audio"]["duration_seconds"])
        ls = lines(doc)
        primary = [line for line in ls if line.get("lead_text", line.get("original_text", "")).strip()
                   and not str(line.get("event_type", "")).lower() in {"vocal_adlib", "adlib_only", "interjection"}]
        flags = []
        for line in primary:
            if line["end"] <= line["start"]:
                flags.append({"type": "zero_duration_primary", "line_id": line["line_id"]})
            elif line["end"] - line["start"] < 0.10:
                flags.append({"type": "primary_duration_lt_0.10", "line_id": line["line_id"]})
            if line["end"] > duration + 0.01:
                flags.append({"type": "line_beyond_audio", "line_id": line["line_id"]})
        ordered = sorted(primary, key=lambda x: (x["start"], x["end"]))
        for prev, nxt in itertools.pairwise(ordered):
            gap = nxt["start"] - prev["end"]
            if gap > 5:
                flags.append({"type": "bounded_gap_gt_5s", "start": prev["end"],
                              "end": nxt["start"], "length": round(gap, 3),
                              "from": prev["line_id"], "to": nxt["line_id"]})
        result.append({"song": song, "flags": flags})
    return {"songs": result, "scope": "static red-flag audit; no automatic changes outside target songs"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "focus_0_40.json").write_text(json.dumps(focus_report(), indent=2, ensure_ascii=False) + "\n")
    (OUT / "chemistry_outro_structure.json").write_text(json.dumps(chemistry_report(), indent=2, ensure_ascii=False) + "\n")
    (OUT / "catalog_red_flags.json").write_text(json.dumps(catalog_red_flags(), indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
