"""Deterministic subtitle-ready completion of weak lyric timing."""
from __future__ import annotations

from copy import deepcopy

DEFAULT_ESTIMATED_LINES = frozenset({
    "section_001_line_004", "section_001_line_006",
    "section_009_line_002", "section_009_line_010",
})


def build_estimated_document(parsed, duration: float, song_id: str, audio_path: str) -> dict:
    """Create a complete subtitle schedule when no acoustic timing exists."""
    all_lines = parsed.lines
    weights = [max(1.0, float(len(line.tokens) or sum(len(line.adlibs) for _ in [0])))
               for line in all_lines]
    gap = 0.12 * max(0, len(parsed.sections) - 1)
    available = max(1.0, duration - gap)
    scale = available / sum(weights)
    cursor = 0.0
    rendered_sections = []
    offset = 0
    for section_index, section in enumerate(parsed.sections):
        rows = []
        section_start = cursor
        for line in section.lines:
            line_duration = max(0.45, weights[offset] * scale)
            start, end = cursor, min(duration, cursor + line_duration)
            token_count = max(1, len(line.tokens))
            words = [{"text": token, "start": round(start + (end - start) * i / token_count, 3),
                      "end": round(start + (end - start) * (i + 1) / token_count, 3),
                      "confidence": 0.0, "timing_source": "line_estimate",
                      "acoustic_supported": False} for i, token in enumerate(line.tokens)]
            rows.append({"line_id": line.line_id, "source_line": line.source_line,
                         "original_text": line.original_text, "lead_text": line.lead_text,
                         "adlibs": line.adlibs, "start": round(start, 3), "end": round(end, 3),
                         "confidence": 0.0, "matched_tokens": 0,
                         "confidence_components": {"estimated": 1.0},
                         "acoustic_start": None, "acoustic_end": None,
                         "total_tokens": len(line.tokens), "words": words,
                         "timing_source": "estimated", "estimated_timing": True,
                         "acoustic_supported": False})
            cursor = end
            offset += 1
        rendered_sections.append({"section_id": section.section_id, "label": section.label,
                                  "start": round(section_start, 3), "end": round(cursor, 3),
                                  "confidence": 0.0, "lines": rows})
        if section_index < len(parsed.sections) - 1:
            cursor = min(duration, cursor + 0.12)
    return {"schema_version": "1.0", "song_id": song_id,
            "audio": {"path": audio_path, "duration_seconds": duration},
            "alignment": {"method": "deterministic_token_weighted_schedule",
                           "acoustic_evidence": False}, "sections": rendered_sections,
            "diagnostics": {"timing_policy": "estimated; no acoustic timing available",
                            "authoritative_line_count": len(all_lines),
                            "estimated_line_count": len(all_lines)},
            "authoritative_lyrics": {"path": parsed.path, "sha256": parsed.sha256}}


def _valid_anchor(line: dict) -> bool:
    return float(line.get("end", 0.0)) > float(line.get("start", 0.0)) + 0.01


def _anchor(lines: list[dict], index: int, direction: int, duration: float) -> float:
    cursor = index + direction
    while 0 <= cursor < len(lines):
        if _valid_anchor(lines[cursor]):
            return float(lines[cursor]["end" if direction < 0 else "start"])
        cursor += direction
    return 0.0 if direction < 0 else duration


def complete_estimated_lines(document: dict, duration: float,
                             line_ids: set[str] | frozenset[str] = DEFAULT_ESTIMATED_LINES,
                             min_duration: float = 0.65) -> dict:
    """Fill selected weak line events inside their nearest temporal bounds.

    The copy retains all authoritative text and direct evidence. Only selected
    lines receive display timing marked ``estimated``; this function never adds
    acoustic support or changes word-level direct-token metrics.
    """
    result = deepcopy(document)
    flat_lines = [line for section in result["sections"] for line in section["lines"]]
    anchor_lines = deepcopy(flat_lines)
    positions = {line["line_id"]: index for index, line in enumerate(flat_lines)}
    for section in result["sections"]:
        lines = section["lines"]
        for line in lines:
            if line["line_id"] not in line_ids:
                continue
            index = positions[line["line_id"]]
            previous_end = _anchor(anchor_lines, index, -1, duration)
            next_start = _anchor(anchor_lines, index, 1, duration)
            next_start = max(next_start, previous_end)
            available = max(0.0, next_start - previous_end)
            start = previous_end
            end = min(duration, start + max(min_duration, available))
            if end > next_start and available > 0:
                end = next_start
            if end <= start:
                end = min(duration, start + min_duration)
            line["start"], line["end"] = round(start, 3), round(end, 3)
            line["acoustic_start"], line["acoustic_end"] = None, None
            line["timing_source"] = "estimated"
            line["estimated_timing"] = True
            line["acoustic_supported"] = False
            line["confidence"] = 0.0
            line["confidence_components"] = {"estimated": 1.0}
            tokens = line.get("words", [])
            if tokens:
                span = (end - start) / len(tokens)
                for word_index, word in enumerate(tokens):
                    word["start"] = round(start + word_index * span, 3)
                    word["end"] = round(start + (word_index + 1) * span, 3)
                    word["confidence"] = 0.0
                    word["timing_source"] = "line_estimate"
                    word["acoustic_supported"] = False
    return result


def estimated_line_ids(document: dict) -> list[str]:
    return [line["line_id"] for section in document["sections"] for line in section["lines"]
            if line.get("timing_source") == "estimated"]
