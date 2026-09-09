"""Repeat-occurrence cadence transfer for structurally identical lyric sections."""
from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateLine:
    index: int
    relative_start: float
    relative_end: float
    start_fraction: float
    end_fraction: float
    duration: float
    confidence: float
    direct: bool
    edge_score: float


def affine_warp(anchor: float, scale: float = 1.0, *, minimum: float = 0.85,
                maximum: float = 1.15) -> tuple[float, float]:
    """Return a conservative affine offset/scale pair."""
    return float(anchor), max(minimum, min(maximum, float(scale)))


def _origin(section: dict) -> float:
    lines = section.get("lines", [])
    return float(lines[0]["start"]) if lines else float(section.get("start", 0.0))


def build_template(section: dict) -> list[TemplateLine]:
    lines = section.get("lines", [])
    origin = _origin(section)
    duration = max(0.01, float(lines[-1]["end"]) - origin) if lines else 1.0
    result = []
    for index, line in enumerate(lines):
        start, end = float(line["start"]), float(line["end"])
        words = line.get("words", [])
        direct = [word for word in words if word.get("acoustic_supported")]
        edge_score = 1.0
        if words:
            edge_score = (float(bool(words[0].get("acoustic_supported"))) +
                          float(bool(words[-1].get("acoustic_supported")))) / 2.0
        result.append(TemplateLine(index=index, relative_start=start - origin,
                                   relative_end=end - origin,
                                   start_fraction=(start - origin) / duration,
                                   end_fraction=(end - origin) / duration,
                                   duration=max(0.0, end - start),
                                   confidence=float(line.get("confidence", 0.0)),
                                   direct=bool(direct), edge_score=edge_score))
    return result


def robust_consensus(templates: list[list[TemplateLine]]) -> list[TemplateLine]:
    """Median consensus, retaining the strongest occurrence's quality fields."""
    if not templates:
        return []
    count = min(len(template) for template in templates)
    result = []
    for index in range(count):
        rows = [template[index] for template in templates]
        result.append(TemplateLine(
            index=index,
            relative_start=statistics.median(row.relative_start for row in rows),
            relative_end=statistics.median(row.relative_end for row in rows),
            start_fraction=statistics.median(row.start_fraction for row in rows),
            end_fraction=statistics.median(row.end_fraction for row in rows),
            duration=statistics.median(row.duration for row in rows),
            confidence=max(row.confidence for row in rows),
            direct=any(row.direct for row in rows),
            edge_score=statistics.median(row.edge_score for row in rows),
        ))
    return result


def transfer(template: list[TemplateLine], anchor: float, scale: float = 1.0) -> list[dict]:
    """Transfer relative line bounds, preserving the template's provenance."""
    _, scale = affine_warp(anchor, scale)
    return [{"index": row.index, "start": round(anchor + scale * row.relative_start, 3),
             "end": round(anchor + scale * row.relative_end, 3),
             "warp_a": round(anchor, 3), "warp_b": round(scale, 5)} for row in template]


def occurrence_score(section: dict) -> float:
    template = build_template(section)
    if not template:
        return 0.0
    direct = sum(row.direct for row in template) / len(template)
    edges = sum(row.edge_score for row in template) / len(template)
    confidence = sum(row.confidence for row in template) / len(template)
    estimated = sum(not row.direct for row in template) / len(template)
    return 0.4 * direct + 0.25 * edges + 0.25 * confidence + 0.1 * (1.0 - estimated)


def has_independent_occurrence_evidence(section: dict) -> bool:
    """Require acoustic support before a repeated occurrence can be promoted.

    Cadence-only rows deliberately do not count: a template can shape an
    occurrence that has already been heard, but it cannot create one from a
    duplicate lyric block alone.
    """
    lines = section.get("lines", [])
    return any(bool(line.get("acoustic_supported")) or any(
        bool(word.get("acoustic_supported")) for word in line.get("words", [])
    ) for line in lines)


def can_promote_repeat_template(section: dict) -> bool:
    """Return whether repeat cadence is eligible for this occurrence."""
    return has_independent_occurrence_evidence(section)
