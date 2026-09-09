from legendary_trap.repeat_templates import (
    affine_warp,
    build_template,
    can_promote_repeat_template,
    robust_consensus,
    transfer,
)


def _section(offset: float, scale: float = 1.0) -> dict:
    return {"lines": [{"start": offset, "end": offset + 1.0 * scale, "confidence": .9,
                        "words": [{"acoustic_supported": True}]},
                       {"start": offset + 1.2 * scale, "end": offset + 2.4 * scale,
                        "confidence": .8, "words": [{"acoustic_supported": True}]}]}


def test_consensus_uses_relative_occurrence_cadence() -> None:
    consensus = robust_consensus([build_template(_section(10)), build_template(_section(50, 1.05))])
    assert round(consensus[1].relative_start, 2) == 1.23
    assert transfer(consensus, 100)[1]["start"] == 101.23


def test_affine_scale_is_clamped() -> None:
    assert affine_warp(10, 2.0) == (10.0, 1.15)
    assert affine_warp(10, 0.1) == (10.0, 0.85)


def test_template_has_direct_and_edge_quality() -> None:
    template = build_template(_section(0))
    assert template[0].direct is True
    assert template[0].edge_score == 1.0


def test_cadence_cannot_create_an_unheard_occurrence() -> None:
    unsupported = {"lines": [{"words": [{"acoustic_supported": False}],
                               "acoustic_supported": False}]}
    supported = {"lines": [{"words": [{"acoustic_supported": True}],
                             "acoustic_supported": False}]}
    assert can_promote_repeat_template(unsupported) is False
    assert can_promote_repeat_template(supported) is True
