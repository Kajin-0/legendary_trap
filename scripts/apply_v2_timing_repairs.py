"""Apply only the approved surgical v2 subtitle-boundary repairs."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def repair_song(song_id: str, updates: dict[str, float]) -> list[dict]:
    path = ROOT / "output" / song_id / "timing.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    changed = []
    for section in document.get("sections", []):
        for line in section.get("lines", []):
            line_id = line.get("line_id")
            if line_id not in updates:
                continue
            old = float(line["end"])
            new = round(float(updates[line_id]), 3)
            if new < float(line["start"]):
                raise ValueError(f"repair would invert {song_id}:{line_id}")
            line["end"] = new
            changed.append({"line_id": line_id, "old_end": old, "new_end": new,
                            "text": line["original_text"]})
    if len(changed) != len(updates):
        seen = {row["line_id"] for row in changed}
        raise KeyError(f"missing repair lines for {song_id}: {set(updates) - seen}")
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return changed


def main() -> None:
    changed = {
        "slidin": repair_song("slidin", {
            "section_003_line_002": 27.240,
            "section_004_line_011": 79.580,
        }),
        "chokehold": repair_song("chokehold", {
            "section_006_line_002": 129.900,
        }),
        "commin_long_ways": repair_song("commin_long_ways", {
            "section_002_line_008": 34.880,
        }),
    }
    print(json.dumps(changed, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
