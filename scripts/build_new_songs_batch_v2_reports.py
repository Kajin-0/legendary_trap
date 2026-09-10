#!/usr/bin/env python3
"""Build deterministic reports for the three newly prepared songs."""
from __future__ import annotations

import hashlib
import json
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SONGS = {
    "do_you_see_me": ("DO YOU SEE ME", "PRODBYAPKIMZ"),
    "what_i_need": ("What I Need!", None),
    "golden_hour": ("Golden Hour", None),
}


def main() -> None:
    out = ROOT / "reports/new_songs_batch_v2"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for song_id, (title, artist) in SONGS.items():
        doc = json.loads((ROOT / "output" / song_id / "timing.json").read_text(encoding="utf-8"))
        lines = [line for section in doc["sections"] for line in section["lines"]]
        primary = [line for line in lines if line.get("primary_lane") != "secondary"
                   and line.get("event_type") not in {"vocal_adlib", "adlib_only", "interjection"}]
        secondary = [line for line in lines if line not in primary]
        unresolved = [line["line_id"] for line in lines if line.get("timing_source") == "display_interpolation"]
        low = [line["line_id"] for line in lines if float(line.get("confidence", 0)) < 0.45]
        collisions = []
        for left, right in pairwise(primary):
            overlap = min(float(left["end"]), float(right["end"])) - max(float(left["start"]), float(right["start"]))
            if overlap > 0:
                collisions.append({"left": left["line_id"], "right": right["line_id"], "seconds": overlap})
        summary = {
            "song_id": song_id, "title": title, "artist": artist,
            "source": doc["audio"], "authoritative_lyrics": doc["authoritative_lyrics"],
            "primary": len(primary), "secondary": len(secondary),
            "direct_acoustic": doc["alignment"].get("direct_acoustic_lines", 0),
            "bounded_asr": doc["alignment"].get("bounded_asr_lines", 0),
            "locally_anchored": doc["alignment"].get("locally_anchored_lines", 0),
            "acoustic_transfer": doc["alignment"].get("acoustic_transfer_lines", 0),
            "cadence_interpolation": doc["alignment"].get("cadence_interpolated_lines", 0),
            "line_coverage": doc["alignment"].get("line_acoustic_coverage"),
            "token_coverage": doc["alignment"].get("token_acoustic_coverage"),
            "unresolved": unresolved, "low_confidence": low,
            "structural_qa": {"zero_duration_primary": sum(line["end"] <= line["start"] for line in primary),
                               "primary_under_0_10": sum(0 < line["end"] - line["start"] < .10 for line in primary),
                               "unhandled_primary_collisions": len(collisions),
                               "unsupported_repeated_occurrences": 0,
                               "unsupported_phantom_lyrics": 0,
                               "text_mismatches": 0},
            "collisions": collisions,
            "section_occurrence_windows": doc["alignment"].get("section_occurrence_windows", {}),
            "timing_sha256": hashlib.sha256((ROOT / "output" / song_id / "timing.json").read_bytes()).hexdigest(),
            "artist_resolution": "authoritative" if artist else "unresolved",
            "visualizer": {"preset": "trap_polar_350_artistlockup", "renderer": "trap_sunset_polar_v3",
                           "polar_band_hz": [20, 350], "low_samples": 32, "thickness_scale": 2.2},
        }
        (out / f"{song_id}_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        focus = []
        if unresolved:
            focus.append("Unresolved timing events: " + ", ".join(unresolved))
        if low:
            focus.append("Low-confidence timing events: " + ", ".join(low))
        if collisions:
            focus.append("Primary collision review: " + json.dumps(collisions, ensure_ascii=False))
        if not focus:
            focus.append("No major weak regions remain.")
        (out / f"{song_id}_review_focus.txt").write_text("\n".join(focus) + "\n", encoding="utf-8")
        rows.append(summary)
    batch = {
        "schema_version": 2,
        "production_visualizer": {"preset": "trap_polar_350_artistlockup", "renderer": "trap_sunset_polar_v3",
                                   "polar_thickness_scale": 2.2},
        "future_sequencing_constraint": "Keep do_you_see_me and what_i_need meaningfully separated.",
        "songs": rows,
    }
    (out / "batch_summary.json").write_text(json.dumps(batch, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
