from pathlib import Path

from legendary_trap.render import build_filter


def test_render_filter_is_audio_reactive_and_subtitle_bound() -> None:
    value = build_filter(Path("/tmp/focus.ass"), "focus")
    assert "showwaves" in value
    assert "subtitles='/tmp/focus.ass'" in value
    assert "s=1920x1080" in value


def test_render_filter_escapes_subtitle_colons() -> None:
    value = build_filter(Path("/tmp/a:b.ass"), "focus")
    assert "a\\:b.ass" in value
