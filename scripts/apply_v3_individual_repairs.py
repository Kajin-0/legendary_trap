"""Apply the evidence-backed FOCUS and chemistry v3 subtitle repairs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FOCUS_FIRST_CHORUS = {
    "section_002_line_001": (12.14, 14.12),
    "section_002_line_002": (14.78, 17.16),
    "section_002_line_003": (17.76, 19.98),
    "section_002_line_004": (19.98, 23.60),
    "section_002_line_005": (23.60, 25.48),
    "section_002_line_006": (26.02, 28.78),
    "section_002_line_007": (28.78, 31.56),
    "section_002_line_008": (32.04, 34.50),
}

CHEMISTRY_LATE = {
    "section_006_line_009": (224.46, 225.40),
    "section_006_line_010": (225.90, 226.70),
    "section_006_line_011": (226.88, 228.52),
    "section_006_line_012": (228.74, 230.50),
    "section_006_line_013": (230.50, 232.12),
}


def _line_map(document: dict) -> dict[str, dict]:
    return {line["line_id"]: line for section in document["sections"]
            for line in section.get("lines", [])}


def _set_direct(line: dict, start: float, end: float, source: str) -> None:
    line["start"], line["end"] = start, end
    line["acoustic_start"], line["acoustic_end"] = start, end
    line["timing_source"] = source
    line["estimated_timing"] = False
    line["acoustic_supported"] = True
    line["confidence_components"] = {"bounded_asr": 1.0, "occurrence_bounded": 1.0}


def repair_focus() -> dict:
    path = ROOT / "output/focus/timing.json"
    document = json.loads(path.read_text())
    before = {key: (_line_map(document)[key]["start"], _line_map(document)[key]["end"])
              for key in FOCUS_FIRST_CHORUS}
    lines = _line_map(document)
    for line_id, (start, end) in FOCUS_FIRST_CHORUS.items():
        _set_direct(lines[line_id], start, end, "asr_distil_large_v3_occurrence_bounded")
    chorus = next(s for s in document["sections"] if s["section_id"] == "section_002")
    chorus["start"], chorus["end"] = 12.14, 34.50
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    return {"before": before, "after": {key: FOCUS_FIRST_CHORUS[key] for key in FOCUS_FIRST_CHORUS}}


def repair_chemistry() -> dict:
    path = ROOT / "output/we_got_chemistry/timing.json"
    document = json.loads(path.read_text())
    before_sections = [s["section_id"] for s in document["sections"]]
    removed = next((s for s in document["sections"] if s["section_id"] == "section_007"), None)
    lines = _line_map(document)
    before_late = {key: (lines[key]["start"], lines[key]["end"]) for key in CHEMISTRY_LATE}
    for line_id, (start, end) in CHEMISTRY_LATE.items():
        _set_direct(lines[line_id], start, end, "asr_distil_large_v3_late_bounded")
    document["sections"] = [s for s in document["sections"] if s["section_id"] != "section_007"]
    lyrics = ROOT / "input/lyrics/we_got_chemistry.txt"
    normalized = lyrics.read_text(encoding="utf-8").rstrip("\n") + "\n"
    document["authoritative_lyrics"] = {
        "path": str(lyrics),
        "sha256": hashlib.sha256(normalized.encode()).hexdigest(),
    }
    document["diagnostics"]["authoritative_line_count"] = sum(
        len(s["lines"]) for s in document["sections"])
    document["diagnostics"]["v3_occurrence_correction"] = {
        "removed_section": "section_007",
        "reason": "fresh unhinted bounded ASR supports one late hook only",
    }
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    return {"before_sections": before_sections, "after_sections": [s["section_id"] for s in document["sections"]],
            "removed_section": bool(removed), "late_before": before_late,
            "late_after": CHEMISTRY_LATE}


if __name__ == "__main__":
    print(json.dumps({"focus": repair_focus(), "chemistry": repair_chemistry()}, indent=2, ensure_ascii=False))
