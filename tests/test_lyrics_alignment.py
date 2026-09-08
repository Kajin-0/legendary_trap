from pathlib import Path

from legendary_trap.alignment import AcousticToken, align_tokens
from legendary_trap.lyrics import normalize, parse_lyrics

ROOT = Path(__file__).resolve().parents[1]


def test_parser_preserves_apple_lines_and_sections() -> None:
    parsed = parse_lyrics(ROOT / "input/lyrics/apple.txt", "apple")
    assert len(parsed.sections) == 6
    assert parsed.lines[0].original_text == "Apple"
    assert parsed.lines[0].lead_text == "Apple"
    assert parsed.lines[0].tokens == ["apple"]
    assert parsed.lines[-1].original_text == "But now you got me singing, got me singing"


def test_parenthetical_is_separate_without_rewriting_display_text(tmp_path: Path) -> None:
    path = tmp_path / "lyrics.txt"
    path.write_text("[Verse]\nFocus (hide that shit)\n", encoding="utf-8")
    line = parse_lyrics(path, "x").lines[0]
    assert line.original_text == "Focus (hide that shit)"
    assert line.lead_text == "Focus"
    assert line.adlibs == ["hide that shit"]
    assert line.tokens == ["focus"]


def test_alignment_is_monotonic_and_uses_authoritative_tokens() -> None:
    acoustic = [AcousticToken("hello", 1.0, 1.2, .9), AcousticToken("world", 1.3, 1.5, .8)]
    matches, coverage, unresolved = align_tokens(["hello", "world"], acoustic)
    assert coverage == 1.0
    assert unresolved == 0
    assert [matches[i].text for i in sorted(matches)] == ["hello", "world"]
    assert matches[0].start < matches[1].start


def test_alignment_normalization_handles_numbers_and_slang() -> None:
    assert normalize("Nineteen") != normalize("19")
    assert normalize("workin' at Five Guys") == "workin at five guys"
