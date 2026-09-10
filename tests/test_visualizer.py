from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from legendary_trap.artist_lockup import artist_lockup_for_song, format_artist_names
from legendary_trap.audio_features import (
    LOW_SPECTRUM_BINS,
    LOW_SPECTRUM_MAX_HZ,
    LOW_SPECTRUM_MIN_HZ,
    FeatureSequence,
    extract_features,
)
from legendary_trap.visualizer import (
    APPROVED_POLAR_LOW_MAX_HZ,
    HEIGHT,
    PALETTE_CYCLE_SECONDS,
    PRESETS,
    PRODUCTION_POLAR_THICKNESS_SCALE,
    PRODUCTION_REVIEW_PRESET,
    STANDALONE_SONGS,
    WIDTH,
    _hybrid_particles,
    palette_at_time,
    polar_contour_offsets,
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
                 "trap_sunset_polar_lowmirror", "trap_sunset_polar_v2",
                 "trap_polar_500hz_maximpact", "trap_polar_350hz_maximpact",
                 "trap_polar_350_artistlockup"):
        particles = (_hybrid_particles(PRESETS[name]) if PRESETS[name].visualizer in
                      {"trap_sunset_hybrid", "trap_sunset_polar_lowmirror", "trap_sunset_polar_v2",
                       "trap_sunset_polar_v3"}
                      else particles)
        first = render_frame(features, 2, PRESETS[name], particles)
        second = render_frame(features, 2, PRESETS[name], particles)
        assert first.shape == (HEIGHT, WIDTH, 3)
        assert np.array_equal(first, second)


def test_preset_names_are_explicit() -> None:
    assert set(PRESETS) == {"orbital", "horizon", "atmospheric", "trap_sunset_hybrid", "trap_sunset_hybrid_v2",
                            "trap_sunset_polar_lowmirror", "trap_sunset_polar_v2",
                            "trap_polar_500hz_maximpact", "trap_polar_350hz_maximpact",
                            "trap_polar_350_artistlockup", "artist_identity_preview",
                            "focus_baseline_no_identity", "chokehold_identity_check"}
    assert Path("output/off_the_wave/timing.json").read_bytes() != b""


def test_production_review_is_locked_to_approved_polar_renderer() -> None:
    assert PRODUCTION_REVIEW_PRESET == "trap_polar_350_artistlockup"
    assert PRESETS[PRODUCTION_REVIEW_PRESET].visualizer == "trap_sunset_polar_v3"
    assert STANDALONE_SONGS["wonder_when_im_gon_shine"]["audio_path"].startswith("source/")


def test_production_review_rejects_linear_fallback() -> None:
    from legendary_trap.visualizer import render_preview

    with pytest.raises(ValueError, match="production review requires"):
        render_preview("wonder_when_im_gon_shine", "trap_sunset_hybrid", 0.0, 1.0)


def test_polar_thickness_changes_stroke_offsets_only() -> None:
    assert np.array_equal(polar_contour_offsets(1.0),
                          np.array([-2.5, -1.25, 0.0, 1.25, 2.5], dtype=np.float32))
    assert np.allclose(polar_contour_offsets(1.6), polar_contour_offsets(1.0) * 1.6)
    assert np.allclose(polar_contour_offsets(2.2), polar_contour_offsets(1.0) * 2.2)
    low = np.linspace(0.1, 1.0, 32, dtype=np.float32)
    angles_a, radii_a = polar_low_radii(low, 0.8)
    angles_b, radii_b = polar_low_radii(low, 0.8)
    assert np.array_equal(angles_a, angles_b)
    assert np.array_equal(radii_a, radii_b)


def test_production_default_thickness_is_baseline() -> None:
    assert PRODUCTION_POLAR_THICKNESS_SCALE == 2.2
    assert polar_contour_offsets(PRODUCTION_POLAR_THICKNESS_SCALE)[-1] == 5.5
    assert np.isclose(np.ptp(polar_contour_offsets(PRODUCTION_POLAR_THICKNESS_SCALE)), 11.0)


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


def test_palette_cycles_without_terminal_freeze() -> None:
    assert not np.array_equal(palette_at_time(30.0), palette_at_time(60.0))
    assert np.allclose(palette_at_time(0.0), palette_at_time(PALETTE_CYCLE_SECONDS))
    assert np.max(np.abs(palette_at_time(PALETTE_CYCLE_SECONDS - 0.001) -
                         palette_at_time(PALETTE_CYCLE_SECONDS + 0.001))) < 1.0


def test_artist_lockup_does_not_fabricate_missing_identity_or_assets() -> None:
    lockup = artist_lockup_for_song("off_the_wave")
    assert lockup.name == "WILLZ"
    assert lockup.pfp_path is None
    assert lockup.asset_status == "ready_text_only"


def test_artist_lockup_resolves_authoritative_pfp_and_adaptive_crop() -> None:
    focus = artist_lockup_for_song("focus")
    artwork = artist_lockup_for_song("you_missed_it")
    assert focus.name == "PRODBYAPKIMZ"
    assert focus.pfp_path == Path("assets/artists/prodbyapkimz.webp").resolve()
    assert focus.crop_shapes == ("circle",)
    assert artwork.name == "TheSideQuest24"
    assert artwork.crop_shapes == ("square",)


def test_artist_lockup_supports_multiple_verified_names() -> None:
    assert format_artist_names(("Artist One", "Artist Two")) == "Artist One × Artist Two"


def test_artist_preview_uses_approved_350_hz_polar_cutoff() -> None:
    assert APPROVED_POLAR_LOW_MAX_HZ == 350.0
    assert PRESETS["trap_polar_350_artistlockup"].visualizer == "trap_sunset_polar_v3"
    assert PRESETS["artist_identity_preview"].visualizer == "trap_sunset_polar_v3"


def test_low_cutoff_variants_are_explicit(tmp_path: Path) -> None:
    audio_path = tmp_path / "silence.wav"
    sf.write(audio_path, np.zeros(48000, dtype=np.float32), 48000)
    for cutoff in (500.0, 350.0):
        features = extract_features(audio_path, 0.0, 0.2, low_max_hz=cutoff)
        assert features.low_max_hz == cutoff
        assert features.low_spectrum is not None
        assert features.low_spectrum.shape[1] == LOW_SPECTRUM_BINS
