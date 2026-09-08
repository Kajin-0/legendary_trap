"""Small, bounded timing repairs based on existing evidence and lyric cadence.

This module deliberately does not run ASR.  It only repairs visibly broken
events in named regions while retaining the canonical lyric text and all
events outside those regions.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _line(document: dict, line_id: str) -> dict:
    for section in document["sections"]:
        for line in section["lines"]:
            if line["line_id"] == line_id:
                return line
    raise KeyError(line_id)


def _set(line: dict, start: float, end: float, source: str = "estimated") -> None:
    line["start"], line["end"] = round(start, 3), round(end, 3)
    line["timing_source"] = source
    line["estimated_timing"] = source != "asr"
    line["acoustic_supported"] = source == "asr"
    if source != "asr":
        line["acoustic_start"], line["acoustic_end"] = None, None
        line["confidence"] = 0.0
        line["confidence_components"] = {"estimated": 1.0}
        words = line.get("words", [])
        if words:
            span = (end - start) / len(words)
            for index, word in enumerate(words):
                word["start"] = round(start + index * span, 3)
                word["end"] = round(start + (index + 1) * span, 3)
                word["timing_source"] = "line_estimate"
                word["acoustic_supported"] = False
                word["confidence"] = 0.0


def _record(changes: list[dict], line: dict, old: tuple[float, float]) -> None:
    if (line["start"], line["end"]) != old:
        changes.append({"line_id": line["line_id"], "old_start": old[0],
                        "old_end": old[1], "new_start": line["start"],
                        "new_end": line["end"], "timing_source": line.get("timing_source")})


def polish(song_id: str, document: dict) -> tuple[dict, list[dict], list[str]]:
    """Return a copy with only the documented weak region repaired."""
    result = copy.deepcopy(document)
    changes: list[dict] = []
    regions: list[str] = []

    def set_line(line_id: str, start: float, end: float, source: str = "estimated") -> None:
        line = _line(result, line_id)
        old = (line["start"], line["end"])
        _set(line, start, end, source)
        _record(changes, line, old)

    if song_id == "commin_long_ways":
        regions = ["intro", "outro"]
        set_line("section_001_line_001", 0.0, 1.2)
        set_line("section_001_line_003", 3.82, 4.18)
        set_line("section_007_line_003", 150.9, 151.22)
        set_line("section_007_line_005", 154.4, 156.2)
    elif song_id == "focus":
        regions = ["intro", "outro"]
        set_line("section_001_line_004", 0.9, 1.8)
        set_line("section_001_line_006", 4.96, 5.21)
        set_line("section_009_line_002", 220.17, 220.82)
        set_line("section_009_line_010", 238.3, 239.5)
    elif song_id == "we_got_chemistry":
        regions = ["opening", "outro"]
        set_line("section_001_line_001", 12.66, 14.56, "asr_distil_large_v3")
        set_line("section_001_line_010", 29.98, 30.65)
        set_line("section_001_line_011", 30.65, 31.22)
        # The final hook repeats the opening hook.  Reuse its measured
        # cadence at the existing final-hook anchor rather than interpolating
        # the whole song.
        opening = result["sections"][0]["lines"]
        final = next(s["lines"] for s in result["sections"] if s["section_id"] == "section_007")
        anchor = 226.44
        opening_by_index = {i: l for i, l in enumerate(opening[:13])}
        cursor = anchor
        for index, line in enumerate(final[:13]):
            source_line = opening_by_index[index]
            duration = max(0.35, float(source_line["end"]) - float(source_line["start"]))
            gap = 0.08 if index else 0.0
            start, end = cursor + gap, cursor + gap + duration
            set_line(line["line_id"], start, end,
                     "asr_distil_large_v3" if index == 0 else "repeated_section_cadence")
            cursor = end
    elif song_id == "slidin":
        regions = ["late verse display pacing"]
        # Existing acoustic starts are retained.  Only extend the final two
        # display spans to avoid rushed flashes; these are not new evidence.
        set_line("section_004_line_011", 78.06, 79.72, "existing_acoustic_display")
        set_line("section_004_line_012", 79.58, 82.54, "existing_acoustic_display")
    elif song_id == "you_missed_it":
        regions = ["intro", "outro"]
        # The bracketed intro is present in the authoritative source but was
        # stretched over the first chorus. Keep it complete and compact.
        bounds = [(0.0, 0.8), (0.92, 1.7), (1.82, 2.6), (2.72, 3.5), (3.62, 4.55)]
        for index, (start, end) in enumerate(bounds, 1):
            set_line(f"section_001_line_{index:03d}", start, end)
    elif song_id == "apple":
        regions = ["second chorus", "bridge/verse transition"]
        set_line("section_002_line_004", 21.38, 25.68)
        bounds = [(96.3, 99.5), (99.8, 103.2), (103.5, 107.0), (107.3, 110.9)]
        for index, (start, end) in enumerate(bounds, 5):
            set_line(f"section_005_line_{index:03d}", start, end,
                     "existing_acoustic_display" if index == 5 else "estimated")
        set_line("section_006_line_002", 112.56, 113.02)

    result.setdefault("diagnostics", {})["targeted_sync_polish"] = True
    result["diagnostics"]["polish_regions"] = regions
    return result, changes, regions


def apply(song_id: str) -> dict:
    path = ROOT / "output" / song_id / "timing.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    polished, changes, regions = polish(song_id, document)
    path.write_text(json.dumps(polished, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"song_id": song_id, "regions": regions, "changes": changes}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("song_id", choices=["commin_long_ways", "focus", "we_got_chemistry",
                                             "slidin", "you_missed_it", "apple"])
    args = parser.parse_args()
    print(json.dumps(apply(args.song_id), indent=2))
