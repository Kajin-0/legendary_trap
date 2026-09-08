"""Bounded repeat-template cleanup for the two reviewed songs."""
from __future__ import annotations

import json
from pathlib import Path

from .local_events import map_sparse_events
from .repeat_templates import build_template, robust_consensus, transfer

ROOT = Path(__file__).resolve().parents[2]


def _section(document: dict, section_id: str) -> dict:
    return next(section for section in document["sections"] if section["section_id"] == section_id)


def _set_bounds(line: dict, start: float, end: float, source: str,
                *, acoustic_core: tuple[float, float] | None = None) -> None:
    old_start, old_end = line["start"], line["end"]
    line.setdefault("acoustic_core_start", acoustic_core[0] if acoustic_core else old_start)
    line.setdefault("acoustic_core_end", acoustic_core[1] if acoustic_core else old_end)
    line["structural_start"], line["structural_end"] = round(start, 3), round(end, 3)
    line["display_start"], line["display_end"] = round(start, 3), round(end, 3)
    line["start"], line["end"] = round(start, 3), round(end, 3)
    line["timing_source"] = source
    line["estimated_timing"] = source not in {"asr", "asr_distil_large_v3"}
    line["acoustic_supported"] = source in {"asr", "asr_distil_large_v3"}
    if line["estimated_timing"]:
        line["confidence"] = 0.0
        line["confidence_components"] = {source: 1.0}
    if source != "repeat_template_edge_reconstruction" and line.get("words"):
        span = (end - start) / len(line["words"])
        for index, word in enumerate(line["words"]):
            word["start"] = round(start + index * span, 3)
            word["end"] = round(start + (index + 1) * span, 3)
            word["timing_source"] = "line_estimate"
            word["acoustic_supported"] = False
            word["confidence"] = 0.0


def _cached_segments(song_id: str, minimum: float, maximum: float) -> list[dict]:
    path = ROOT / "work" / song_id / "asr-base.en.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return [segment for segment in data["segments"]
            if segment["end"] > minimum and segment["start"] < maximum]


def apply_you_missed_it(document: dict) -> dict:
    result = json.loads(json.dumps(document))
    chorus_ids = ["section_002", "section_004", "section_006"]
    sections = [_section(result, section_id) for section_id in chorus_ids]
    donors = [build_template(section) for section in sections[1:]]
    consensus = robust_consensus(donors)
    target = sections[0]
    anchor = target["lines"][0]["start"]
    transferred = transfer(consensus, anchor, 1.0)
    changes = []
    # Intro is a secondary lane. Use the existing base-ASR activity peaks as
    # bounded display evidence; do not let these rows move Chorus #1.
    intro = _section(result, "section_001")
    intro_bounds = [(0.96, 1.5), (1.64, 1.86), (3.42, 3.96),
                    (5.74, 6.2), (7.34, 11.56)]
    for line, (start, end) in zip(intro["lines"], intro_bounds):
        old = (line["start"], line["end"])
        _set_bounds(line, start, end, "estimated")
        line["secondary_lane_evidence"] = "asr-base.en local intro activity"
        changes.append({"line_id": line["line_id"], "text": line["original_text"],
                        "old_start": old[0], "old_end": old[1], "new_start": start,
                        "new_end": end, "source": line["timing_source"],
                        "donor_occurrences": [], "warp_a": None, "warp_b": None,
                        "direct_anchor_count": 0, "reason": "bounded secondary intro activity"})
    # Preserve the strong direct lines; repair only the weak leading edge of
    # line 6, whose current core starts at the matched word "bitch".
    line = target["lines"][5]
    old = (line["start"], line["end"])
    proposed = transferred[5]
    new_start = proposed["start"]
    new_end = max(proposed["end"], old[1])
    _set_bounds(line, new_start, new_end, "repeat_template_edge_reconstruction",
                acoustic_core=old)
    changes.append({"line_id": line["line_id"], "text": line["original_text"],
                    "old_start": old[0], "old_end": old[1], "new_start": line["start"],
                    "new_end": line["end"], "source": line["timing_source"],
                    "donor_occurrences": chorus_ids[1:], "warp_a": anchor, "warp_b": 1.0,
                    "direct_anchor_count": 3,
                    "reason": "missing leading tokens reconstructed from chorus consensus"})

    # The cached base pass supplies bounded local acoustic regions for the
    # sparse outro. Identity remains authoritative lyric text; these are
    # explicitly local ad-lib display events, not lead-token evidence.
    outro = _section(result, "section_007")
    acoustic = [
        {"start": 153.36, "end": 156.54},
        {"start": 158.34, "end": 160.28},
        {"start": 160.46, "end": 163.18},
        {"start": 165.18, "end": 166.52},
    ]
    events = [
        {"acoustic_segment_index": 0},
        {"next_acoustic_segment_index": 1},
        {"acoustic_segment_index": 1},
        {"acoustic_segment_index": 2},
        {"next_acoustic_segment_index": 3},
        {"next_acoustic_segment_index": 3},
        {"acoustic_segment_index": 3},
    ]
    mapped = map_sparse_events(events, acoustic, 153.36, 166.52)
    for line, mapped_event in zip(outro["lines"], mapped):
        old = (line["start"], line["end"])
        source = "local_adlib_asr" if mapped_event["timing_source"] == "asr" else "estimated"
        _set_bounds(line, mapped_event["start"], mapped_event["end"], source,
                    acoustic_core=(mapped_event["start"], mapped_event["end"]) if source != "estimated" else None)
        line["acoustic_supported"] = False
        line["lexically_recognized"] = False
        changes.append({"line_id": line["line_id"], "text": line["original_text"],
                        "old_start": old[0], "old_end": old[1], "new_start": line["start"],
                        "new_end": line["end"], "source": line["timing_source"],
                        "donor_occurrences": [], "warp_a": None, "warp_b": None,
                        "direct_anchor_count": 0, "reason": "bounded sparse outro event"})
    result.setdefault("diagnostics", {})["repeat_template_cleanup"] = True
    result["diagnostics"]["repeat_template_donors"] = chorus_ids[1:]
    result["diagnostics"]["intro_secondary_activity_window"] = [0.96, 11.56]
    return result, changes, {"chorus_occurrences": chorus_ids, "chorus_consensus": [row.__dict__ for row in consensus]}


def apply_commin_outro(document: dict) -> tuple[dict, list[dict]]:
    result = json.loads(json.dumps(document))
    section = _section(result, "section_007")
    changes = []
    updates = {
        "section_007_line_002": (146.24, 149.9),
        "section_007_line_003": (149.9, 151.22),
        "section_007_line_005": (154.4, 162.78),
    }
    for line in section["lines"]:
        if line["line_id"] not in updates:
            continue
        old = (line["start"], line["end"])
        start, end = updates[line["line_id"]]
        _set_bounds(line, start, end, "local_boundary_estimate")
        changes.append({"line_id": line["line_id"], "text": line["original_text"],
                        "old_start": old[0], "old_end": old[1], "new_start": start,
                        "new_end": end, "source": line["timing_source"],
                        "donor_occurrences": [], "warp_a": None, "warp_b": None,
                        "direct_anchor_count": 1,
                        "reason": "bounded late-outro boundary reconstruction"})
    result.setdefault("diagnostics", {})["commin_outro_cleanup"] = True
    return result, changes


def apply(song_id: str) -> dict:
    path = ROOT / "output" / song_id / "timing.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    if song_id == "you_missed_it":
        result, changes, metadata = apply_you_missed_it(document)
    elif song_id == "commin_long_ways":
        result, changes = apply_commin_outro(document)
        metadata = {}
    else:
        raise ValueError(song_id)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"song_id": song_id, "changes": changes, "metadata": metadata}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("song_id", choices=["you_missed_it", "commin_long_ways"])
    args = parser.parse_args()
    print(json.dumps(apply(args.song_id), indent=2, ensure_ascii=False))
