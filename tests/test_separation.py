from pathlib import Path

import pytest

from legendary_trap.separation import separated_word_provenance, validate_stem


def test_missing_or_empty_stem_cannot_be_validated(tmp_path: Path) -> None:
    result = validate_stem(tmp_path / "missing.wav")
    assert result["valid"] is False
    assert result["silent_output"] is True


def test_separated_word_retains_explicit_provenance() -> None:
    word = separated_word_provenance("focus", 1.2, 1.6, "roformer", "kim", .8)
    assert word["timing_source"] == "asr_distil_large_v3_roformer_vocals"
    assert word["separator"]["model"] == "kim"


def test_separated_word_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError):
        separated_word_provenance("focus", 1.2, 1.6, "roformer", "kim", 1.1)
