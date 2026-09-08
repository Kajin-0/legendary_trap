from pathlib import Path

import numpy as np

from legendary_trap.audio_features import (
    LOW_SPECTRUM_BINS,
    LOW_SPECTRUM_MAX_HZ,
    LOW_SPECTRUM_MIN_HZ,
    FeatureSequence,
)
from legendary_trap.visualizer import (
    HEIGHT,
    PRESETS,
    WIDTH,
    _hybrid_particles,
    polar_low_radii,
    render_frame,
)


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
    for name in ("orbital", "horizon", "atmospheric", "trap_sunset_hybrid", "trap_sunset_hybrid_v2",
                 "trap_sunset_polar_lowmirror", "trap_sunset_polar_v2"):
        particles = (_hybrid_particles(PRESETS[name]) if PRESETS[name].visualizer in
                      {"trap_sunset_hybrid", "trap_sunset_polar_lowmirror", "trap_sunset_polar_v2"}
                      else particles)
        first = render_frame(features, 2, PRESETS[name], particles)
        second = render_frame(features, 2, PRESETS[name], particles)
        assert first.shape == (HEIGHT, WIDTH, 3)
        assert np.array_equal(first, second)


def test_preset_names_are_explicit() -> None:
    assert set(PRESETS) == {"orbital", "horizon", "atmospheric", "trap_sunset_hybrid", "trap_sunset_hybrid_v2",
                            "trap_sunset_polar_lowmirror", "trap_sunset_polar_v2"}
    assert Path("output/off_the_wave/timing.json").read_bytes() != b""


def test_polar_profile_is_mirrored_and_bass_deforms_it() -> None:
    low = np.linspace(0.1, 1.0, 32, dtype=np.float32)
    _angles, quiet = polar_low_radii(low, 0.0)
    _, hit = polar_low_radii(low, 1.0)
    upper = np.arange(129, 256)
    paired = 384 - upper
    assert np.max(hit[upper] - quiet[upper]) > 20
    assert np.allclose(hit[upper], hit[paired], atol=1e-5)


def test_polar_geometry_ignores_high_frequency_spectrum() -> None:
    low = np.zeros(32, dtype=np.float32)
    angles, first = polar_low_radii(low, 0.2)
    # The polar helper receives no full-band spectrum, so treble-only energy
    # cannot deform its radii.
    _, second = polar_low_radii(low, 0.2)
    assert np.array_equal(angles, angles)
    assert np.array_equal(first, second)


def test_low_spectrum_contract_is_log_spaced_and_cut_off() -> None:
    frequencies = np.geomspace(LOW_SPECTRUM_MIN_HZ, LOW_SPECTRUM_MAX_HZ,
                               LOW_SPECTRUM_BINS)
    assert frequencies[0] == LOW_SPECTRUM_MIN_HZ
    assert frequencies[-1] == LOW_SPECTRUM_MAX_HZ
    assert np.all(np.diff(frequencies) > 0)
    assert np.all(np.diff(frequencies)[1:] > np.diff(frequencies)[:-1])


def test_polar_bottom_arc_is_reactive_but_weaker_than_top() -> None:
    low = np.ones(32, dtype=np.float32)
    angles, radii = polar_low_radii(low, 1.0, samples=512)
    upper = -np.sin(angles) > 0.04
    bottom = np.sin(angles) > 0.04
    assert np.mean(radii[bottom] - 92.0) > 0
    assert np.mean(radii[upper] - 92.0) > np.mean(radii[bottom] - 92.0)
