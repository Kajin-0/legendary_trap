from pathlib import Path

import numpy as np

from legendary_trap.audio_features import FeatureSequence
from legendary_trap.visualizer import HEIGHT, PRESETS, WIDTH, _hybrid_particles, render_frame


def _features() -> FeatureSequence:
    n = 4
    return FeatureSequence(30, np.full((n, 16), 0.4, dtype=np.float32),
                           np.linspace(0.1, 0.8, n, dtype=np.float32),
                           np.linspace(0.2, 0.7, n, dtype=np.float32),
                           np.linspace(0.3, 0.6, n, dtype=np.float32),
                           np.full(n, 0.4, dtype=np.float32),
                           np.full(n, 0.2, dtype=np.float32))


def test_presets_have_required_visual_dimensions_and_are_deterministic() -> None:
    features = _features()
    particles = (np.array([[0.2, 0.3]], dtype=np.float32), np.array([0.5], dtype=np.float32),
                 np.array([0.1], dtype=np.float32))
    for name in ("orbital", "horizon", "atmospheric", "trap_sunset_hybrid"):
        particles = (_hybrid_particles(PRESETS[name]) if name == "trap_sunset_hybrid" else particles)
        first = render_frame(features, 2, PRESETS[name], particles)
        second = render_frame(features, 2, PRESETS[name], particles)
        assert first.shape == (HEIGHT, WIDTH, 3)
        assert np.array_equal(first, second)


def test_preset_names_are_explicit() -> None:
    assert set(PRESETS) == {"orbital", "horizon", "atmospheric", "trap_sunset_hybrid"}
    assert Path("output/off_the_wave/timing.json").read_bytes() != b""
