from pathlib import Path

from legendary_trap.render import build_filter
from legendary_trap.subtitle_render import write_visual_ass


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


def test_artist_lockup_is_optional_and_separate_from_lyrics(tmp_path: Path) -> None:
    document = {"sections": [{"lines": [{"start": 0.0, "end": 2.0,
                                            "original_text": "A centered lyric"}]}]}
    path = tmp_path / "artist.ass"
    write_visual_ass(document, path, "off the wave", lyric_font="Barlow Condensed",
                     lyric_size=90, artist_name="Artist Name", artist_font="Super Crown")
    value = path.read_text(encoding="utf-8")
    assert "Style: Artist,Super Crown,27" in value
    assert "\\an7\\pos(72,62)" in value
    assert "Style: Lyric,Barlow Condensed,90" in value
    assert "{\\an5\\pos(960,540)\\fad(160,220)}A centered lyric" in value
