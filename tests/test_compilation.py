import hashlib
from pathlib import Path

import pytest

from legendary_trap.compilation import build_track_plan, load_catalog


def test_playlist_contains_the_eight_authoritative_tracks() -> None:
    songs, artists = load_catalog()
    assert songs["track_order"] == [
        "apple", "chokehold", "commin_long_ways", "focus", "off_the_wave",
        "slidin", "we_got_chemistry", "you_missed_it",
    ]
    assert artists["artists"] == {}


def test_compilation_offsets_are_deterministic_and_local_timing_is_untouched() -> None:
    durations = {song: 100.0 + index for index, song in enumerate(load_catalog()[0]["track_order"])}
    plans = build_track_plan(durations, transition_seconds=1.5)
    assert [plan.master_start for plan in plans] == [0.0, 101.5, 204.0, 307.5, 412.0, 517.5, 624.0, 731.5]
    assert all(plan.local_start == 0.0 for plan in plans)


def test_missing_or_invalid_duration_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing positive duration"):
        build_track_plan({"apple": 0.0})


def test_metadata_files_are_repository_local() -> None:
    assert Path("configs/songs.json").is_file()
    assert Path("configs/artists.json").is_file()


def test_artist_catalog_does_not_change_canonical_timing() -> None:
    timing = Path("output/off_the_wave/timing.json")
    digest = hashlib.sha256(timing.read_bytes()).hexdigest()
    assert digest == "a067ae1a3f5cb9094244084c3be0430e803a67c74e223378e3332e265d29081b"
