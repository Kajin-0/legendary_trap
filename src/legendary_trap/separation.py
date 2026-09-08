"""Safety helpers for optional bounded vocal-separation evidence.

The separator itself is intentionally not a project dependency. These helpers
make it difficult for a future adapter to turn a missing/invalid stem into
acoustic coverage or to lose provenance.
"""
from __future__ import annotations

from pathlib import Path


def validate_stem(path: Path, duration_seconds: float | None = None,
                  tolerance_seconds: float = 0.25) -> dict[str, object]:
    """Validate basic stem conditions without treating them as recognition."""
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    valid = exists and size > 44
    if duration_seconds is not None:
        valid = valid and duration_seconds >= 0.0
    return {"path": str(path), "exists": exists, "size_bytes": size,
            "duration_seconds": duration_seconds, "tolerance_seconds": tolerance_seconds,
            "valid": valid, "silent_output": not valid}


def separated_word_provenance(text: str, start: float, end: float,
                              separator: str, model: str, confidence: float) -> dict[str, object]:
    """Build explicit provenance for a word recognized on a separated stem."""
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be within [0, 1]")
    if start < 0.0 or end < start:
        raise ValueError("invalid word timing")
    return {"text": text, "start": start, "end": end,
            "timing_source": "asr_distil_large_v3_roformer_vocals",
            "acoustic_supported": True, "lexically_recognized": True,
            "separator": {"architecture": "melband_roformer", "model": model},
            "confidence": confidence}
