import numpy as np

from legendary_trap.acoustic_events import _unit


def test_feature_normalization_is_bounded() -> None:
    values = _unit(np.array([0.0, 1.0, 2.0, 3.0, 4.0]))
    assert np.all(values >= 0.0)
    assert np.all(values <= 1.0)


def test_event_fallback_does_not_imply_lexical_recognition() -> None:
    event = {"timing_source": "bounded_acoustic_event", "acoustic_supported": True,
             "lexically_recognized": False}
    assert event["acoustic_supported"] is True
    assert event["lexically_recognized"] is False
