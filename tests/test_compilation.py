import hashlib
from pathlib import Path

import pytest

from legendary_trap.compilation import build_track_plan, load_catalog


def test_playlist_contains_the_sixteen_authoritative_tracks() -> None:
    songs, artists = load_catalog()
    assert songs["track_order"] == [
        "apple", "chokehold", "commin_long_ways", "focus", "off_the_wave",
        "slidin", "we_got_chemistry", "you_missed_it", "wonder_when_im_gon_shine",
        "on_a_trance", "do_you_see_me", "hella_racks", "difference",
        "purple_satellites", "golden_hour", "what_i_need",
    ]
    assert set(songs["track_order"]).issubset(songs["songs"])
    assert set(artists["artists"]).issuperset({
        "jayc3", "OppTalk", "PRODBYAPKIMZ", "TheSideQuest24", "WILLZ", "VonKai", "KarmaisMagic"
    })


def test_compilation_offsets_are_deterministic_and_local_timing_is_untouched() -> None:
    durations = {song: 100.0 + index for index, song in enumerate(load_catalog()[0]["track_order"])}
    plans = build_track_plan(durations, transition_seconds=1.5)
    assert [plan.master_start for plan in plans] == [
        0.0, 101.5, 204.0, 307.5, 412.0, 517.5, 624.0, 731.5,
        840.0, 949.5, 1060.0, 1171.5, 1284.0, 1397.5, 1512.0, 1627.5,
    ]
    assert all(plan.local_start == 0.0 for plan in plans)


def test_missing_or_invalid_duration_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing positive duration"):
        build_track_plan({"apple": 0.0})


def test_metadata_files_are_repository_local() -> None:
    assert Path("configs/songs.json").is_file()
    assert Path("configs/artists.json").is_file()


def test_all_supplied_artist_assets_resolve() -> None:
    artists = load_catalog()[1]["artists"]
    assert set(artists).issuperset({
        "jayc3", "OppTalk", "PRODBYAPKIMZ", "TheSideQuest24", "WILLZ", "VonKai", "KarmaisMagic"
    })
    assert all(Path(record["pfp"]).is_file() for record in artists.values() if record["pfp"])


def test_authoritative_song_mappings_and_display_names_are_exact() -> None:
    songs = load_catalog()[0]
    expected = {
        "apple": "KarmaisMagic", "chokehold": "OppTalk", "commin_long_ways": "PRODBYAPKIMZ",
        "focus": "PRODBYAPKIMZ", "off_the_wave": "WILLZ", "slidin": "jayc3",
        "we_got_chemistry": "VonKai", "you_missed_it": "TheSideQuest24",
    }
    assert {song: songs["songs"][song]["artists"][0] for song in expected} == expected
    assert {song: songs["songs"][song]["artists"][0] for song in (
        "wonder_when_im_gon_shine", "on_a_trance", "do_you_see_me", "hella_racks", "difference", "purple_satellites",
        "golden_hour", "what_i_need"
    )} == {
        "wonder_when_im_gon_shine": "berb", "on_a_trance": "lilshitty", "hella_racks": "ken carson",
        "do_you_see_me": "PRODBYAPKIMZ", "difference": "noek95", "purple_satellites": "SILL-E",
        "golden_hour": "Maverick", "what_i_need": "mushi",
    }
    assert load_catalog()[1]["artists"]["VonKai"]["display_name"] == "VonKai"
    assert load_catalog()[1]["artists"]["TheSideQuest24"]["display_name"] == "TheSideQuest24"


def test_artist_catalog_does_not_change_canonical_timing() -> None:
    timing = Path("output/off_the_wave/timing.json")
    digest = hashlib.sha256(timing.read_bytes()).hexdigest()
    assert digest == "a067ae1a3f5cb9094244084c3be0430e803a67c74e223378e3332e265d29081b"
