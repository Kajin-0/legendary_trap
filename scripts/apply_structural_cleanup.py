"""Repair only the four v3 catalog structural defects."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

UPDATES = {
    "chokehold": {
        "section_006_line_003": (129.900, 129.950, "asr_direct_adlib"),
        "section_006_line_004": (129.950, 130.032, "bounded_local_adlib_interpolation"),
    },
    "we_got_chemistry": {
        "section_002_line_019": (65.200, 65.300, "bounded_local_adlib_interpolation"),
        "section_002_line_028": (80.040, 80.180, "asr_direct_adlib"),
    },
}


def apply(song_id: str, updates: dict[str, tuple[float, float, str]]) -> list[dict]:
    path = ROOT / "output" / song_id / "timing.json"
    document = json.loads(path.read_text())
    by_id = {line["line_id"]: line for section in document["sections"] for line in section["lines"]}
    changed = []
    for line_id, (start, end, source) in updates.items():
        line = by_id[line_id]
        old = {"start": line["start"], "end": line["end"],
               "timing_source": line.get("timing_source"),
               "event_type": line.get("event_type"), "primary_lane": line.get("primary_lane")}
        line["start"], line["end"] = start, end
        line["timing_source"] = source
        line["event_type"] = "vocal_adlib"
        line["primary_lane"] = "secondary"
        line["lane"] = "secondary"
        line["estimated_timing"] = source != "asr_direct_adlib"
        line["acoustic_supported"] = True
        line["confidence_components"] = {"local_adlib_evidence": 1.0}
        changed.append({"line_id": line_id, "text": line["original_text"],
                        "old": old, "new": {"start": start, "end": end,
                                             "timing_source": source,
                                             "event_type": "vocal_adlib", "lane": "secondary"}})
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    return changed


if __name__ == "__main__":
    print(json.dumps({song: apply(song, updates) for song, updates in UPDATES.items()},
                     indent=2, ensure_ascii=False))
