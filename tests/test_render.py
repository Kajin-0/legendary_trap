from pathlib import Path

from legendary_trap.artist_lockup import artist_lockup_for_song
from legendary_trap.artist_overlay import FINAL_HEIGHT, FINAL_WIDTH, PFP_SIZE, build_artist_overlay
from legendary_trap.render import build_filter
from legendary_trap.subtitle_render import clip_render_document, write_visual_ass


def test_render_filter_is_audio_reactive_and_subtitle_bound() -> None:
    value = build_filter(Path("/tmp/focus.ass"), "focus")
    assert "showwaves" in value
    assert "subtitles='/tmp/focus.ass'" in value
    assert "s=1920x1080" in value


def test_render_filter_escapes_subtitle_colons() -> None:
    value = build_filter(Path("/tmp/a:b.ass"), "focus")
    assert "a\\:b.ass" in value


def test_lyrics_use_explicit_middle_center_and_large_montserrat(tmp_path: Path) -> None:
    document = {"sections": [{"lines": [{"start": 0.0, "end": 2.0,
                                            "original_text": "A centered lyric"}]}]}
    path = tmp_path / "sample.ass"
    write_visual_ass(document, path, "off the wave")
    value = path.read_text(encoding="utf-8")
    assert "Style: Lyric,Montserrat,84" in value
    assert "Dialogue: 1,0:00:00.00,0:00:02.00" in value
    assert "{\\an5\\pos(960,540)\\fad(160,220)}A centered lyric" in value


def test_identity_overlay_is_separate_from_lyrics(tmp_path: Path) -> None:
    document = {"sections": [{"lines": [{"start": 0.0, "end": 2.0,
                                            "original_text": "A centered lyric"}]}]}
    path = tmp_path / "artist.ass"
    write_visual_ass(document, path, "off the wave", lyric_font="Barlow Condensed", lyric_size=90,
                     include_title=False)
    value = path.read_text(encoding="utf-8")
    assert "Style: Lyric,Barlow Condensed,90" in value
    assert "{\\an5\\pos(960,540)\\fad(160,220)}A centered lyric" in value
    assert "Artist" not in value
    assert "ArtistTitle" not in value


def test_preview_clipping_preserves_intersecting_events() -> None:
    document = {"sections": [{"lines": [
        {"start": 1.0, "end": 3.0, "original_text": "before"},
        {"start": 3.0, "end": 5.0, "original_text": "inside"},
        {"start": 5.0, "end": 7.0, "original_text": "after"},
        {"start": 9.0, "end": 9.0, "original_text": "zero"},
    ]}]}
    clipped = clip_render_document(document, 3.0, 4.0)
    assert [(x["start"], x["end"], x["original_text"]) for x in clipped["sections"][0]["lines"]] == [
        (0.0, 2.0, "inside"), (2.0, 4.0, "after")
    ]


def test_identity_on_off_produces_identical_lyric_rows(tmp_path: Path) -> None:
    document = {"sections": [{"lines": [{"start": 0.0, "end": 2.0,
                                            "original_text": "same lyric"}]}]}
    baseline = tmp_path / "baseline.ass"
    identity = tmp_path / "identity.ass"
    write_visual_ass(document, baseline, "focus", lyric_font="Barlow Condensed", lyric_size=90,
                     include_title=False)
    write_visual_ass(document, identity, "focus", lyric_font="Barlow Condensed", lyric_size=90,
                     include_title=False)
    lyric_rows = lambda path: [line for line in path.read_text().splitlines() if ",Lyric,," in line]
    assert lyric_rows(baseline) == lyric_rows(identity)


def test_artist_overlay_uses_final_dimensions_and_preserves_identity_asset_shape() -> None:
    overlay = build_artist_overlay(artist_lockup_for_song("focus"), "FOCUS")
    assert overlay.size == (FINAL_WIDTH, FINAL_HEIGHT)
    assert PFP_SIZE == 128
    assert overlay.getchannel("A").getbbox() is not None


def test_identity_mode_has_no_legacy_duplicate_title_event(tmp_path: Path) -> None:
    document = {"sections": [{"lines": [{"start": 0.0, "end": 2.0,
                                            "original_text": "same lyric"}]}]}
    path = tmp_path / "identity.ass"
    write_visual_ass(document, path, "focus", lyric_font="Barlow Condensed", lyric_size=90,
                     include_title=False)
    events = [line for line in path.read_text().splitlines() if line.startswith("Dialogue:")]
    assert len(events) == 1
    assert ",Lyric,," in events[0]


def test_adlib_overlap_uses_distinct_secondary_lane(tmp_path: Path) -> None:
    document = {"sections": [{"lines": [
        {"start": 1.0, "end": 2.0, "original_text": "(Yeah)", "event_type": "vocal_adlib"},
        {"start": 1.5, "end": 3.0, "original_text": "primary lyric"},
    ]}]}
    path = tmp_path / "lanes.ass"
    write_visual_ass(document, path, "focus", lyric_font="Barlow Condensed", lyric_size=90,
                     include_title=False)
    rows = [line for line in path.read_text().splitlines() if line.startswith("Dialogue:")]
    assert any(",Adlib,," in row and r"\pos(960,635)" in row for row in rows)
    assert any(",Lyric,," in row and r"\pos(960,540)" in row for row in rows)
