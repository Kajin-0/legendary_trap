from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_new_song_and_artist_registrations_preserve_track_order() -> None:
    artists = json.loads((ROOT / "configs/artists.json").read_text())["artists"]
    songs = json.loads((ROOT / "configs/songs.json").read_text())
    expected = {
        "berb": "berb", "lilshitty": "lilshitty", "ken carson": "ken carson",
        "noek95": "noek95", "SILL-E": "SILL-E",
    }
    assert {key: artists[key]["display_name"] for key in expected} == expected
    assert songs["track_order"] == ["apple", "chokehold", "commin_long_ways", "focus",
                                    "off_the_wave", "slidin", "we_got_chemistry", "you_missed_it"]
    assert songs["songs"]["on_a_trance"]["artists"] == ["lilshitty"]
    assert songs["songs"]["hella_racks"]["artists"] == ["ken carson"]
    assert songs["songs"]["difference"]["artists"] == ["noek95"]
    assert songs["songs"]["purple_satellites"]["artists"] == ["SILL-E"]


def test_new_song_timing_exports_are_canonical_and_structurally_sound() -> None:
    for song in ("on_a_trance", "hella_racks", "difference", "purple_satellites"):
        output = ROOT / "output" / song
        document = json.loads((output / "timing.json").read_text())
        lines = [line for section in document["sections"] for line in section["lines"]]
        primary = [line for line in lines if line["event_type"] != "vocal_adlib"]
        assert all(line["end"] > line["start"] for line in primary)
        assert all(line["end"] - line["start"] >= 0.10 for line in primary)
        assert all((output / f"{song}.{ext}").exists() for ext in ("ass", "srt", "vtt"))
        assert all(line["original_text"] in (output / f"{song}.ass").read_text()
                   for line in lines)


def test_nine_frozen_timing_hashes() -> None:
    expected = {
        "apple": "8275d3c4b3aa1b8a9ab3141cc3dc90c5e0abce27b7c4493118a17094899d9b88",
        "chokehold": "1cc68e6703aa62417e058acd2e723e1739c0efc8b94e39807dc2265a9e698385",
        "commin_long_ways": "3f59eadd57cf6acc28e398a4bbbdb2cc45ddc903aa25094ed3a594b69b432b85",
        "focus": "63435609fc1091fc14947765ce5869dc283e2173c9ee0edb61fdfb4996f1fc8a",
        "off_the_wave": "a067ae1a3f5cb9094244084c3be0430e803a67c74e223378e3332e265d29081b",
        "slidin": "283f141b9d0bab6433d28b7cc5ffacad6ba2d0db7027689f87e00e2ba1f71524",
        "we_got_chemistry": "2719ca38ecfaba9c38c1c397a501b5ebd61a9b1fc82e5a4fcbd31228d1141979",
        "you_missed_it": "18d088ba77baa50b186948237aeeb93b560a418252300c3b55ab23ed75e5097f",
        "wonder_when_im_gon_shine": "9d9d18d410163fb173e7d86bc40e306e6cb7973d251c563eea7c7d118b68ec15",
    }
    for song, digest in expected.items():
        assert hashlib.sha256((ROOT / "output" / song / "timing.json").read_bytes()).hexdigest() == digest
