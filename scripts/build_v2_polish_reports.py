"""Build v2 color, overlap, chemistry, gap, and chapter diagnostics."""
from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path

from legendary_trap.visualizer import PALETTE_CYCLE_SECONDS, palette_at_time

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "v2_polish"
ORDER = ["apple", "chokehold", "commin_long_ways", "focus", "off_the_wave",
         "slidin", "we_got_chemistry", "you_missed_it"]


def lines(song_id: str) -> list[dict]:
    doc = json.loads((ROOT / "output" / song_id / "timing.json").read_text(encoding="utf-8"))
    result = []
    for section in doc.get("sections", []):
        for line in section.get("lines", []):
            if float(line["end"]) > float(line["start"]):
                result.append({**line, "section_id": section.get("section_id")})
    return sorted(result, key=lambda x: float(x["start"]))


def secondary(line: dict) -> bool:
    return str(line.get("event_type", "")).lower() in {"vocal_adlib", "adlib_only", "interjection"} or str(line.get("original_text", "")).lstrip().startswith("(")


def build_color() -> dict:
    times = [0, 18, 30, 60, 90, 120, 180, 240, 300, 360]
    values = [{"time": t, "rgb": [round(float(v), 3) for v in palette_at_time(t)]} for t in times]
    return {"cycle_seconds": PALETTE_CYCLE_SECONDS, "samples": values,
            "wrap_delta": float(max(abs(palette_at_time(0) - palette_at_time(PALETTE_CYCLE_SECONDS))))}


def build_overlaps() -> dict:
    catalog = []
    for song in ORDER:
        rows = lines(song)
        for a, b in pairwise(rows):
            overlap = min(float(a["end"]), float(b["end"])) - max(float(a["start"]), float(b["start"]))
            if overlap <= 0:
                continue
            if secondary(a) or secondary(b):
                classification = "intentional_lead_adlib"
            else:
                classification = "sequential_line_timing_collision"
            catalog.append({"song": song, "start": max(float(a["start"]), float(b["start"])),
                            "end": min(float(a["end"]), float(b["end"])),
                            "overlap_seconds": round(overlap, 3),
                            "text_a": a["original_text"], "text_b": b["original_text"],
                            "section_a": a.get("section_id"), "section_b": b.get("section_id"),
                            "event_type_a": a.get("event_type"), "event_type_b": b.get("event_type"),
                            "classification": classification,
                            "handled_by": "secondary_ass_style" if classification == "intentional_lead_adlib" else "surgical_boundary_repair"})
    repairs = [
        {"song": "chokehold", "line_id": "section_006_line_002", "old_end": 130.032, "new_end": 129.900,
         "reason": "direct 50ms primary-primary boundary collision; minimal end clamp"},
        {"song": "commin_long_ways", "line_id": "section_002_line_008", "old_end": 34.920, "new_end": 34.880,
         "reason": "direct 40ms primary-primary boundary collision; minimal end clamp"},
        {"song": "slidin", "line_id": "section_003_line_002", "old_end": 28.54, "new_end": 27.24,
         "reason": "normal consecutive primary lines collided by 1.30s"},
        {"song": "slidin", "line_id": "section_004_line_011", "old_end": 79.72, "new_end": 79.58,
         "reason": "normal consecutive primary lines collided by 0.14s"},
        {"song": "you_missed_it", "lines": ["section_001_line_005", "section_002_line_001"],
         "reason": "intentional vocal adlib over lead; moved to distinct secondary ASS lane"},
    ]
    return {"repairs": repairs, "remaining_overlaps": catalog,
            "unhandled_primary_primary": [x for x in catalog if x["classification"] == "sequential_line_timing_collision"]}


def build_chemistry() -> dict:
    before = [{"line_id": "section_006_line_010", "start": 224.76, "end": 225.41},
              {"line_id": "section_006_line_011", "start": 225.41, "end": 225.68},
              {"line_id": "section_006_line_012", "start": 225.68, "end": 225.68},
              {"line_id": "section_006_line_013", "start": 225.68, "end": 226.14}]
    return {"song": "we_got_chemistry", "target_range": [160.0, 249.24],
            "promoted": False, "reason": "cached late high-capacity evidence maps the repeated outro occurrence ambiguously; no safe local edit was promoted",
            "before": before, "after": before,
            "evidence": {"source": "work/we_got_chemistry/large_whisper/groups.json",
                         "strong_direct_anchor_count": 0,
                         "note": "The cached pass supports alternate boundaries but also assigns repeated lines across section_006/section_007 inconsistently; preserving canonical timing is safer than shifting the final occurrence."}}


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "color_cycle_audit.json").write_text(json.dumps(build_color(), indent=2) + "\n")
    (REPORTS / "subtitle_overlap_audit.json").write_text(json.dumps(build_overlaps(), indent=2, ensure_ascii=False) + "\n")
    (REPORTS / "chemistry_late_alignment.json").write_text(json.dumps(build_chemistry(), indent=2) + "\n")


if __name__ == "__main__":
    main()
