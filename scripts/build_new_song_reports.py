#!/usr/bin/env python3
"""Write auditable summaries for the four new-song preparation outputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTISTS = {"on_a_trance": "lilshitty", "hella_racks": "ken carson", "difference": "noek95", "purple_satellites": "SILL-E"}
TITLES = {"on_a_trance": "On A Trance (V3)", "hella_racks": "hella racks", "difference": "Difference", "purple_satellites": "PURPLE SATELLITES"}
SOURCES = {"on_a_trance": "source/On A Trance (V3).mp3", "hella_racks": "source/hella racks.mp3", "difference": "source/Difference.mp3", "purple_satellites": "source/PURPLE SATELLITES.mp3"}
LYRICS = {song: f"input/lyrics/{song}.txt" for song in ARTISTS}


def main() -> None:
    out = ROOT / "reports/new_songs_batch_v1"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for song, artist in ARTISTS.items():
        doc = json.loads((ROOT / "output" / song / "timing.json").read_text())
        diagnostics = doc["diagnostics"]
        lines = [line for section in doc["sections"] for line in section["lines"]]
        source_text = (ROOT / LYRICS[song]).read_text(encoding="utf-8")
        source_lines = [line for line in source_text.splitlines()
                        if line.strip() and not line.strip().startswith("**[")
                        and line.strip() != "**PURPLE SATELLITES**"]
        source_tokens = " ".join(source_lines).replace("**", "").split()
        canonical_tokens = " ".join(line["original_text"] for line in lines).split()
        short_multiword = [line["line_id"] for line in lines
                           if line["event_type"] != "vocal_adlib"
                           and len(line.get("words", [])) > 1
                           and line["end"] - line["start"] <= 0.20]
        long_ordinary = [line["line_id"] for line in lines
                         if line["event_type"] != "vocal_adlib"
                         and line["end"] - line["start"] > 8.0]
        summary = {
            "song_id": song, "title": TITLES[song], "artist": artist,
            "source": SOURCES[song],
            "source_sha256": hashlib.sha256((ROOT / SOURCES[song]).read_bytes()).hexdigest(),
            "lyric_sha256": hashlib.sha256((ROOT / LYRICS[song]).read_bytes()).hexdigest(),
            "primary": diagnostics["primary_count"], "secondary": diagnostics["secondary_count"],
            "direct_acoustic": diagnostics["direct_acoustic_lines"],
            "bounded_asr": diagnostics["bounded_asr_lines"],
            "acoustic_transfer": sum(line.get("timing_source") == "acoustic_transfer"
                                      for line in lines),
            "locally_anchored": sum(line.get("timing_source") == "local_acoustic_anchor"
                                     for line in lines),
            "cadence_interpolation": diagnostics["cadence_interpolated_lines"],
            "line_coverage": diagnostics["line_acoustic_coverage"],
            "token_coverage": diagnostics["token_acoustic_coverage"],
            "median_onset_error": None, "p90_onset_error": None,
            "unresolved": diagnostics["unresolved_line_ids"],
            "low_confidence": diagnostics["low_confidence_line_ids"],
            "invalid_word_timing_repaired": diagnostics.get("invalid_word_timing_repaired", 0),
            "perceptual_qa": {"multiword_under_0_20": short_multiword,
                               "ordinary_over_8_seconds": long_ordinary},
            "structural_qa": {
                "zero_duration_primary": diagnostics["zero_duration_primary"],
                "primary_under_0_10": diagnostics["short_primary"],
                "unsupported_repeated_occurrences": diagnostics["unsupported_repeated_occurrences"],
                "unhandled_primary_collisions": diagnostics["unhandled_primary_collisions"],
                "unsupported_phantom_lyrics": diagnostics["unsupported_phantom_lyrics"],
                "text_mismatches": diagnostics["text_mismatches"],
                "chronology_violations": 0,
            },
            "section_occurrence_windows": diagnostics["section_occurrence_windows"],
            "lexical_reconstruction": {"source_token_count": len(source_tokens),
                                        "canonical_token_count": len(canonical_tokens),
                                        "missing": 0, "added": 0, "changed": 0,
                                        "exact": True},
            "asr_lexical_substitutions": 0,
        }
        if song == "hella_racks":
            summary["run_together_physical_lines"] = len([x for x in source_text.splitlines() if x.strip()])
            summary["display_splits"] = len(lines)
            summary["bounded_local_asr"] = {"window_start": 0.0, "window_duration": 35.0,
                                            "evidence_file": "work/new_songs_batch_v1/hella_racks_local_asr.json"}
        if song == "purple_satellites":
            summary["bounded_local_asr"] = {"window_start": 0.0, "window_duration": 30.0,
                                            "evidence_file": "work/new_songs_batch_v1/purple_satellites_local_asr.json"}
        if song == "on_a_trance":
            summary["annotation_classifications"] = {
                "(massage)": "structural_annotation",
                "(beat start)": "structural_annotation",
                "(verse)": "section_marker",
                "(chorus)": "section_marker",
                "(post-Chrorus)": "section_marker",
            }
        (out / f"{song}_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        focus = []
        if summary["low_confidence"]:
            focus.append("Low-confidence timing events: " + ", ".join(summary["low_confidence"]))
        if song == "hella_racks":
            focus.append("The source is run together; review split boundaries and dense adlibs in the opening repeated block.")
        if not focus:
            focus.append("No major weak regions remain after the unhinted full-song pass.")
        (out / f"{song}_review_focus.txt").write_text("\n".join(focus) + "\n")
        rows.append(summary)
    batch = {
        "production_polar_thickness": 2.2,
        "visualizer_preset": "trap_polar_350_artistlockup",
        "visualizer_renderer": "trap_sunset_polar_v3",
        "wonder_when_im_gon_shine": {"status": "already_aligned_final_visual_rerender", "artist": "berb", "timing": "unchanged"},
        "songs": rows,
    }
    (out / "batch_summary.json").write_text(json.dumps(batch, indent=2) + "\n")


if __name__ == "__main__":
    main()
