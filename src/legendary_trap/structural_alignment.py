"""Shadow structural alignment diagnostics using existing timing evidence.

No inference is performed here.  The module constrains existing evidence by
section occurrence, separates primary/ad-lib events, and diagnoses missing
line edges before any timing is considered for promotion.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from .lyrics import LyricLine, parse_lyrics

ROOT = Path(__file__).resolve().parents[2]
LEAD_SONGS = ["apple", "chokehold", "commin_long_ways", "focus", "off_the_wave",
              "slidin", "we_got_chemistry", "you_missed_it"]


def _timing_by_source_line(document: dict) -> dict[int, dict]:
    return {line["source_line"]: line for section in document.get("sections", [])
            for line in section.get("lines", [])}


def _direct(word: dict) -> bool:
    return bool(word.get("acoustic_supported")) and word.get("timing_source") in {
        "asr", "asr_distil_large_v3", "ctc_forced_alignment", "singing_forced_alignment",
    }


def _line_edge(line: LyricLine, row: dict | None) -> dict:
    words = row.get("words", []) if row else []
    direct = [index for index, word in enumerate(words) if _direct(word)]
    total = len(line.tokens)
    if not direct or not total:
        return {"line_id": line.line_id, "source_line": line.source_line,
                "section_id": line.section_id, "event_type": line.event_type,
                "primary_lane": line.primary_lane, "total_tokens": total,
                "matched_tokens": len(direct), "first_matched_token_index": None,
                "last_matched_token_index": None, "leading_unmatched_token_count": total,
                "trailing_unmatched_token_count": total, "leading_edge_coverage": 0.0,
                "trailing_edge_coverage": 0.0, "boundary_reconstructed": False}
    first, last = min(direct), max(direct)
    return {"line_id": line.line_id, "source_line": line.source_line,
            "section_id": line.section_id, "event_type": line.event_type,
            "primary_lane": line.primary_lane, "total_tokens": total,
            "matched_tokens": len(direct), "first_matched_token_index": first,
            "last_matched_token_index": last,
            "leading_unmatched_token_count": first,
            "trailing_unmatched_token_count": total - last - 1,
            "leading_edge_coverage": round((total - first) / total, 4),
            "trailing_edge_coverage": round((last + 1) / total, 4),
            "boundary_reconstructed": first > 0 or last < total - 1}


def _local_rate(line: dict, row: dict, neighbors: list[dict]) -> float:
    direct = [w for w in row.get("words", []) if _direct(w)]
    if len(direct) >= 2:
        span = direct[-1]["end"] - direct[0]["start"]
        if span > 0:
            return max(0.10, min(0.75, span / max(1, len(direct))))
    rates = []
    for neighbor in neighbors:
        count = sum(_direct(w) for w in neighbor.get("words", []))
        span = float(neighbor.get("end", 0)) - float(neighbor.get("start", 0))
        if count and span > 0:
            rates.append(span / count)
    return max(0.10, min(0.75, statistics.median(rates) if rates else 0.28))


def boundary_candidate(line: LyricLine, row: dict, edges: dict,
                       neighbors: list[dict]) -> dict | None:
    direct = [w for w in row.get("words", []) if _direct(w)]
    if not direct or not line.tokens:
        return None
    rate = _local_rate(line.__dict__, row, neighbors)
    start = max(float(row["start"]) - edges["leading_unmatched_token_count"] * rate,
                max((float(n["end"]) for n in neighbors if n.get("end") is not None), default=0.0))
    end = min(float(row["end"]) + edges["trailing_unmatched_token_count"] * rate,
              min((float(n["start"]) for n in neighbors if n.get("start") is not None),
                  default=float(row["end"]) + edges["trailing_unmatched_token_count"] * rate))
    if start >= float(row["start"]) and end <= float(row["end"]):
        return None
    return {"line_id": line.line_id, "old_start": row["start"], "old_end": row["end"],
            "candidate_start": round(start, 3), "candidate_end": round(max(start, end), 3),
            "rate_seconds_per_token": round(rate, 4), "reason": "missing_line_edges"}


def evaluate(song_id: str) -> dict:
    manifest = json.loads((ROOT / "song_manifest.json").read_text())
    song = next(item for item in manifest["songs"] if item["id"] == song_id)
    parsed = parse_lyrics(ROOT / song["lyrics_path"], song_id)
    timing = json.loads((ROOT / "output" / song_id / "timing.json").read_text())
    by_source = _timing_by_source_line(timing)
    edge_rows = []
    candidates = []
    for section in parsed.sections:
        for line in section.lines:
            row = by_source.get(line.source_line)
            edge = _line_edge(line, row)
            edge_rows.append(edge)
            if row and line.primary_lane == "lead" and edge["boundary_reconstructed"]:
                neighbor_rows = [by_source.get(x.source_line) for x in section.lines
                                  if by_source.get(x.source_line) and x.source_line != line.source_line]
                candidate = boundary_candidate(line, row, edge, neighbor_rows)
                if candidate:
                    candidates.append(candidate)
    section_map = []
    for section in parsed.sections:
        rows = [by_source.get(line.source_line) for line in section.lines if by_source.get(line.source_line)]
        section_map.append({"section_id": section.section_id, "raw_label": section.raw_label,
                            "structural_role": section.structural_role,
                            "structurally_inferred": section.structural_inferred,
                            "repeat_group": section.repeat_group,
                            "occurrence_index": section.occurrence_index,
                            "occurrence_count": section.occurrence_count,
                            "source_start_line": section.source_start_line,
                            "audio_start": min((r["start"] for r in rows), default=None),
                            "audio_end": max((r["end"] for r in rows), default=None),
                            "line_count": len(section.lines)})
    repeated = [x for x in section_map if x["repeat_group"]]
    primary = [x for x in edge_rows if x["primary_lane"] == "lead" and x["total_tokens"]]
    return {"song_id": song_id, "authoritative_sha256": parsed.sha256,
            "section_count": len(parsed.sections), "line_count": len(parsed.lines),
            "adlib_only_events": sum(x["event_type"] == "adlib_only" for x in edge_rows),
            "section_map": section_map, "repeat_groups": repeated,
            "edge_diagnostics": edge_rows, "boundary_candidates": candidates,
            "leading_edge_failures": sum(x["leading_unmatched_token_count"] > 0 for x in primary),
            "trailing_edge_failures": sum(x["trailing_unmatched_token_count"] > 0 for x in primary),
            "candidate_reconstruction_count": len(candidates),
            "non_target_timing_changes": 0, "shadow_only": True}


def repeated_section_candidate(document: dict, source_section_id: str,
                               target_section_id: str, target_anchor: float,
                               source_start: int = 0, target_start: int = 0,
                               count: int | None = None) -> list[dict]:
    """Copy cadence, not wording/evidence, between two known section occurrences."""
    sections = {s["section_id"]: s for s in document.get("sections", [])}
    source = sections[source_section_id]["lines"][source_start:]
    target = sections[target_section_id]["lines"][target_start:]
    if count is not None:
        source, target = source[:count], target[:count]
    changes = []
    cursor = target_anchor
    previous_source_end = source[0]["start"] if source else 0.0
    for source_line, target_line in zip(source, target):
        source_duration = max(0.35, source_line["end"] - source_line["start"])
        source_gap = max(0.0, source_line["start"] - previous_source_end)
        start = cursor + (0.0 if source_line is source[0] else min(0.36, source_gap))
        end = start + source_duration
        old = (target_line["start"], target_line["end"])
        target_line["start"], target_line["end"] = round(start, 3), round(end, 3)
        target_line["timing_source"] = "repeated_section_cadence"
        target_line["estimated_timing"] = True
        target_line["acoustic_supported"] = False
        target_line["acoustic_start"], target_line["acoustic_end"] = None, None
        target_line["confidence"] = 0.0
        target_line["confidence_components"] = {"repeated_section_cadence": 1.0}
        words = target_line.get("words", [])
        if words:
            span = (end - start) / len(words)
            for index, word in enumerate(words):
                word["start"] = round(start + index * span, 3)
                word["end"] = round(start + (index + 1) * span, 3)
                word["timing_source"] = "line_estimate"
                word["acoustic_supported"] = False
                word["confidence"] = 0.0
        changes.append({"line_id": target_line["line_id"], "old_start": old[0], "old_end": old[1],
                        "new_start": target_line["start"], "new_end": target_line["end"],
                        "timing_source": target_line["timing_source"]})
        cursor = end
        previous_source_end = source_line["end"]
    return changes


def run_all() -> dict:
    reports = {song_id: evaluate(song_id) for song_id in LEAD_SONGS}
    return reports


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("song_id", nargs="?", choices=LEAD_SONGS)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.song_id) if args.song_id else run_all(), indent=2, ensure_ascii=False))
