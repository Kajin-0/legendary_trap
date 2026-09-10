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
    assert songs["track_order"] == [
        "apple", "chokehold", "commin_long_ways", "focus", "off_the_wave", "slidin",
        "we_got_chemistry", "you_missed_it", "wonder_when_im_gon_shine", "on_a_trance",
        "do_you_see_me", "hella_racks", "difference", "purple_satellites", "golden_hour",
        "what_i_need",
    ]
    assert songs["songs"]["on_a_trance"]["artists"] == ["lilshitty"]
    assert songs["songs"]["hella_racks"]["artists"] == ["ken carson"]
    assert songs["songs"]["difference"]["artists"] == ["noek95"]
    assert songs["songs"]["purple_satellites"]["artists"] == ["SILL-E"]


def test_corrective_batch_registers_new_songs_and_pfps_without_guessing() -> None:
    artists = json.loads((ROOT / "configs/artists.json").read_text())["artists"]
    songs = json.loads((ROOT / "configs/songs.json").read_text())["songs"]
    assert artists["SILL-E"]["pfp"] == "assets/artists/SILL-E.webp"
    assert artists["ken carson"]["pfp"] == "assets/artists/kencarson.webp"
    assert artists["noek95"]["pfp"] == "assets/artists/noek95.webp"
    assert songs["do_you_see_me"]["artists"] == ["PRODBYAPKIMZ"]
    assert songs["what_i_need"]["artists"] == ["mushi"]
    assert songs["golden_hour"]["artists"] == ["Maverick"]
    assert json.loads((ROOT / "configs/songs.json").read_text())["track_order"][10] == "do_you_see_me"


def test_targeted_do_and_golden_timing_repairs_are_canonical() -> None:
    for song in ("do_you_see_me", "golden_hour"):
        document = json.loads((ROOT / "output" / song / "timing.json").read_text())
        assert document["alignment"]["unresolved_line_ids"] == []
        assert document["alignment"]["low_confidence_line_ids"] == []
        assert document["alignment"]["zero_duration_primary"] == 0
        assert document["alignment"]["short_primary"] == 0
        assert document["alignment"]["unhandled_primary_collisions"] == 0
        assert all(line["end"] > line["start"] for section in document["sections"]
                   for line in section["lines"])
    golden = json.loads((ROOT / "output/golden_hour/timing.json").read_text())
    target = next(line for section in golden["sections"] for line in section["lines"]
                  if line["line_id"] == "section_001_line_002")
    assert (target["start"], target["end"]) == (1.56, 3.3)


def test_final_artist_identities_resolve_without_duplicates() -> None:
    artists = json.loads((ROOT / "configs/artists.json").read_text())["artists"]
    assert artists["mushi"] == {"display_name": "MUSHI", "pfp": "assets/artists/mushi.jpeg", "crop": "circle"}
    assert "MUSHI" not in artists
    assert artists["Maverick"]["pfp"] == "assets/artists/Maverick.webp"


def test_new_song_structures_and_outputs_exist() -> None:
    for song in ("do_you_see_me", "what_i_need", "golden_hour"):
        document = json.loads((ROOT / "output" / song / "timing.json").read_text())
        assert document["audio"]["duration_seconds"] > 0
        assert all((ROOT / "output" / song / f"{song}.{ext}").exists()
                   for ext in ("ass", "srt", "vtt"))
        assert all(word["start"] <= word["end"]
                   for section in document["sections"] for line in section["lines"]
                   for word in line.get("words", []))


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


def test_hella_opening_has_local_acoustic_support() -> None:
    document = json.loads((ROOT / "output/hella_racks/timing.json").read_text())
    opening = document["sections"][0]["lines"][:7]
    assert all(line["timing_source"] == "local_acoustic_anchor" for line in opening)
    assert all(line["acoustic_support"] and not line["estimated_timing"] for line in opening)
    assert document["diagnostics"]["unresolved_line_ids"] == []


def test_purple_title_and_headings_are_not_rendered_lyrics() -> None:
    document = json.loads((ROOT / "output/purple_satellites/timing.json").read_text())
    lines = [line for section in document["sections"] for line in section["lines"]]
    assert all(line["original_text"] != "**PURPLE SATELLITES**" for line in lines)
    assert all(not line["original_text"].startswith("**[") for line in lines)
    intro = next(section for section in document["sections"] if section["label"].lower() == "intro")
    assert all(line["end"] - line["start"] >= 0.20 for line in intro["lines"][:4])
    assert intro["lines"][3]["end"] - intro["lines"][3]["start"] < 8.0


def test_repaired_word_timings_are_valid_and_monotonic() -> None:
    for song in ("hella_racks", "purple_satellites"):
        document = json.loads((ROOT / "output" / song / "timing.json").read_text())
        for section in document["sections"]:
            for line in section["lines"]:
                words = line.get("words", [])
                assert all(word["start"] <= word["end"] for word in words)
                assert all(words[i]["start"] <= words[i + 1]["start"]
                           for i in range(len(words) - 1))


def test_perceptual_duration_flags_are_clear_for_repaired_openings() -> None:
    for song in ("hella_racks", "purple_satellites"):
        summary = json.loads((ROOT / "reports/new_songs_batch_v1" / f"{song}_summary.json").read_text())
        assert summary["perceptual_qa"]["multiword_under_0_20"] == []
        assert summary["perceptual_qa"]["ordinary_over_8_seconds"] == []


def test_non_target_song_timing_and_subtitle_exports_are_frozen() -> None:
    expected = {
        "wonder_when_im_gon_shine": {
            "timing.json": "9d9d18d410163fb173e7d86bc40e306e6cb7973d251c563eea7c7d118b68ec15",
            "wonder_when_im_gon_shine.ass": "974f600275952f9ed6c54e60356dce771a2f8ae40ae4f5c9daf2d49e29443e66",
            "wonder_when_im_gon_shine.srt": "30c5a9ada2295149371b0e258d38df0afd6ab5a8f542a651e821dcb402c87624",
            "wonder_when_im_gon_shine.vtt": "45203087e8027ba87e1ee00523db09c24626d7b9dd5747b9b500cb5cea7ad196",
        },
        "on_a_trance": {
            "timing.json": "1f9b63afb33f4e593593718111debb069c8d386da1c5e73e139ed7cd40a0ecfa",
            "on_a_trance.ass": "72e23ecf4dfa46433a2a2103950ef0e18ee08d72708bbe442f1f6a67690b1085",
            "on_a_trance.srt": "dff2b7bbd0024faeff5137bbf4548dac8205e3832e2f34d5c5b0feec119e76a9",
            "on_a_trance.vtt": "16d99a8c901a68d1e55c85dfbe74b69ccab7023bd3635b2a4ebe6deaea5f42d0",
        },
        "difference": {
            "timing.json": "cb40f1322c7e77ee814f80ab048f835ec821d3ba79f758ecfc56e9fe0036f42b",
            "difference.ass": "0a66551367cf3e8c8b76bc36c98789dadc6323bc1b31de4ca5ade42bf6fb7903",
            "difference.srt": "26cf5517128d24e4c234e1b1cf4424e5503e9416728650e3ab49a00d409a2465",
            "difference.vtt": "f18a270d2ae8bfe4d20ec1edfc271365f63938bd8c46f2ec8c72ef58bc01fb27",
        },
    }
    for song, files in expected.items():
        for filename, digest in files.items():
            assert hashlib.sha256((ROOT / "output" / song / filename).read_bytes()).hexdigest() == digest
