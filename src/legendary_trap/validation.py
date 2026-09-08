"""Machine-readable canonical timing invariants."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from .lyrics import section_heading


def validate(document: dict, lyric_path: Path, expected_sha256: str, duration: float) -> dict:
    failures, warnings = [], []
    raw = lyric_path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    digest = hashlib.sha256((raw.rstrip("\n") + "\n").encode()).hexdigest()
    if digest != expected_sha256 or document["authoritative_lyrics"]["sha256"] != digest:
        failures.append("authoritative lyric SHA-256 mismatch")
    lines = [line for s in document["sections"] for line in s["lines"]]
    authoritative = [raw_line for raw_line in raw.splitlines()
                     if raw_line.strip() and section_heading(raw_line) is None]
    emitted = [line["original_text"] for line in lines]
    if emitted != authoritative:
        failures.append("emitted authoritative line sequence does not exactly match source")
    if len(emitted) != len(authoritative):
        failures.append("authoritative line count mismatch")
    if len({line["line_id"] for line in lines}) != len(lines): failures.append("duplicate line IDs")
    previous_section, previous_line = -1.0, -1.0
    for s in document["sections"]:
        if s["start"] < previous_section: failures.append("section order violation")
        previous_section = s["start"]
        if s["start"] > s["end"]: failures.append(f"section reversed: {s['section_id']}")
        for line in s["lines"]:
            for value in (line["start"], line["end"], line["confidence"]):
                if not math.isfinite(value): failures.append(f"non-finite value: {line['line_id']}")
            if line["start"] < 0 or line["start"] > line["end"]: failures.append(f"bad line range: {line['line_id']}")
            if line["end"] > duration + 0.25: failures.append(f"line exceeds audio: {line['line_id']}")
            if not 0 <= line["confidence"] <= 1: failures.append(f"bad confidence: {line['line_id']}")
            if line["start"] < previous_line - 0.01: failures.append(f"line order violation: {line['line_id']}")
            previous_line = line["start"]
            for word in line["words"]:
                if word["start"] < line["start"] - .05 or word["end"] > line["end"] + .05:
                    warnings.append(f"word outside line tolerance: {line['line_id']}")
    low = [line["line_id"] for line in lines if line["confidence"] < 0.45]
    if low: warnings.append(f"{len(low)} low-confidence lines")
    return {"valid": not failures, "failures": failures, "warnings": sorted(set(warnings)),
            "line_count": len(lines), "low_confidence_line_ids": low,
            "authoritative_sha256": digest}
