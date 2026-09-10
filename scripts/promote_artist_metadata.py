#!/usr/bin/env python3
"""Resolve the two final artist identities without touching lyric timing."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPPINGS = {"what_i_need": "MUSHI", "golden_hour": "Maverick"}


def timing_content(document: dict) -> list[dict]:
    rows = []
    for section in document["sections"]:
        for line in section["lines"]:
            rows.append({
                "section_id": section["section_id"],
                "occurrence_index": section.get("occurrence_index"),
                "line_id": line["line_id"],
                "authoritative_text": line["original_text"],
                "start": line["start"], "end": line["end"],
                "acoustic_start": line.get("acoustic_start"),
                "acoustic_end": line.get("acoustic_end"),
                "timing_source": line.get("timing_source"),
                "event_type": line.get("event_type"), "lane": line.get("lane"),
                "words": [{"text": word.get("text"), "start": word.get("start"),
                           "end": word.get("end")} for word in line.get("words", [])],
            })
    return rows


def digest(document: dict) -> str:
    payload = json.dumps(timing_content(document), ensure_ascii=False,
                         separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


before = {}
for song_id, artist_name in MAPPINGS.items():
    path = ROOT / "output" / song_id / "timing.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    before[song_id] = digest(document)
    document["artist"] = artist_name
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

after = {}
for song_id in MAPPINGS:
    document = json.loads((ROOT / "output" / song_id / "timing.json").read_text(encoding="utf-8"))
    after[song_id] = digest(document)

report = {
    "what_i_need": {"before": before["what_i_need"], "after": after["what_i_need"],
                    "unchanged": before["what_i_need"] == after["what_i_need"]},
    "golden_hour": {"before": before["golden_hour"], "after": after["golden_hour"],
                    "unchanged": before["golden_hour"] == after["golden_hour"]},
}
out = ROOT / "reports/artist_promotion/timing_content_digest.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
