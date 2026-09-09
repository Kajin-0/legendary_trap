"""Write the deterministic four-event cleanup audit."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/v3_individual_audit/structural_cleanup.json"
TARGETS = {
    "chokehold": ["section_006_line_003", "section_006_line_004"],
    "we_got_chemistry": ["section_002_line_019", "section_002_line_028"],
}


def flatten(document: dict) -> list[tuple[dict, dict]]:
    return [(section, line) for section in document["sections"] for line in section["lines"]]


def catalog_counts() -> dict:
    zero, short = [], []
    for song in ["apple", "chokehold", "commin_long_ways", "focus", "off_the_wave",
                 "slidin", "we_got_chemistry", "you_missed_it"]:
        document = json.loads((ROOT / "output" / song / "timing.json").read_text())
        for section, line in flatten(document):
            secondary = (line.get("event_type") in {"vocal_adlib", "adlib_only", "interjection"}
                         or line.get("lane") == "secondary" or line.get("primary_lane") == "secondary"
                         or str(line.get("original_text", "")).lstrip().startswith("("))
            if secondary:
                continue
            duration = float(line["end"]) - float(line["start"])
            if duration <= 0:
                zero.append(f"{song}:{line['line_id']}")
            elif duration < 0.10:
                short.append(f"{song}:{line['line_id']}")
    return {"zero_duration_primary": zero, "short_primary_lt_0.10": short}


def main() -> None:
    rows = []
    for song, target_ids in TARGETS.items():
        document = json.loads((ROOT / "output" / song / "timing.json").read_text())
        pairs = flatten(document)
        for index, (section, line) in enumerate(pairs):
            if line["line_id"] not in target_ids:
                continue
            primary_neighbors = [(s, l) for s, l in pairs if l.get("primary_lane", "lead") != "secondary"]
            pos = next((i for i, (_, candidate) in enumerate(primary_neighbors)
                        if candidate["line_id"] == line["line_id"]), None)
            previous = next((candidate for _, candidate in reversed(pairs[:index])
                             if candidate.get("primary_lane", "lead") != "secondary"), None)
            following = next((candidate for _, candidate in pairs[index + 1:]
                              if candidate.get("primary_lane", "lead") != "secondary"), None)
            rows.append({"song": song, "section": section["label"],
                         "line_id": line["line_id"], "text": line["original_text"],
                         "start": line["start"], "end": line["end"],
                         "timing_source": line.get("timing_source"),
                         "event_type": line.get("event_type"), "lane": line.get("lane"),
                         "acoustic_supported": line.get("acoustic_supported"),
                         "neighbor_context": {
                             "primary_index": pos,
                             "previous_primary": previous and {
                                 "line_id": previous["line_id"], "text": previous["original_text"],
                                 "start": previous["start"], "end": previous["end"]},
                             "next_primary": following and {
                                 "line_id": following["line_id"], "text": following["original_text"],
                                 "start": following["start"], "end": following["end"]},
                         }})
    report = {"targets": rows, "catalog_invariants_after": catalog_counts(),
              "long_gaps_are_diagnostic_only": True,
              "evidence": {
                  "chokehold": "cached base.en local words 129.90–130.032; high-capacity pass had no usable words",
                  "we_got_chemistry": "cached base.en local words at 65.30 and 80.04–80.18",
              }}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
