from legendary_trap.singing_alignment import _clean_word, _strip_stress


def test_singing_normalization_is_not_authoritative_rewrite() -> None:
    source = "movin’"
    assert _clean_word(source) == "movin"
    assert source == "movin’"


def test_arpabet_stress_is_removed_only_from_alignment_view() -> None:
    assert _strip_stress("AH0") == "AH"
