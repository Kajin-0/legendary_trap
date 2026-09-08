from legendary_trap.ctc_alignment import normalize_ctc


def test_ctc_normalization_is_alignment_only() -> None:
    source = "Whole world movin’ on, but I’m stuck with it"
    assert normalize_ctc(source) == "whole world movin on but im stuck with it"
    assert source == "Whole world movin’ on, but I’m stuck with it"


def test_ctc_normalization_preserves_word_boundaries() -> None:
    assert normalize_ctc("Focus (hide that shit)") == "focus hide that shit"
