"""Deterministic subtitle-ready completion of weak lyric timing."""
from __future__ import annotations

from copy import deepcopy

DEFAULT_ESTIMATED_LINES = frozenset({
    "section_001_line_004", "section_001_line_006",
    "section_009_line_002", "section_009_line_010",
})


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
