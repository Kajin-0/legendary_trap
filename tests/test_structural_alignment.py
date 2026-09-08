from pathlib import Path

from legendary_trap.lyrics import parse_lyrics, section_heading
from legendary_trap.structural_alignment import evaluate


def test_malformed_outro_is_structural_without_mutating_source(tmp_path: Path) -> None:
    source = "[Intro]\n(Yeah)\n[Outro\n(Focus)\n"
    path = tmp_path / "lyrics.txt"
    path.write_text(source, encoding="utf-8")
    parsed = parse_lyrics(path, "x")
    assert section_heading("[Outro") == ("Outro", True)
    assert [section.structural_role for section in parsed.sections] == ["intro", "outro"]
    assert parsed.sections[1].structural_inferred is True
    assert parsed.sha256
    assert path.read_text(encoding="utf-8") == source


def test_adlib_only_rows_use_secondary_lane_and_inline_adlibs_stay_attached(tmp_path: Path) -> None:
    path = tmp_path / "lyrics.txt"
    path.write_text("[Hook]\nLead phrase (yeah)\n(woah)\n", encoding="utf-8")
    parsed = parse_lyrics(path, "x")
    assert parsed.sections[0].lines[0].event_type == "lead_with_adlib"
    assert parsed.sections[0].lines[0].primary_lane == "lead"
    assert parsed.sections[0].lines[0].adlibs == ["yeah"]
    assert parsed.sections[0].lines[1].event_type == "adlib_only"
    assert parsed.sections[0].lines[1].primary_lane == "secondary"


def test_repeated_sections_have_distinct_occurrences(tmp_path: Path) -> None:
    path = tmp_path / "lyrics.txt"
    path.write_text("[Chorus]\nSame line\n[Verse]\nOther line\n[Chorus]\nSame line\n", encoding="utf-8")
    parsed = parse_lyrics(path, "x")
    chorus = [s for s in parsed.sections if s.repeat_group]
    assert len(chorus) == 2
    assert [s.occurrence_index for s in chorus] == [1, 2]
    assert len({s.section_id for s in chorus}) == 2


def test_shadow_evaluation_does_not_overwrite_production_timing() -> None:
    before = Path("output/commin_long_ways/timing.json").read_bytes()
    result = evaluate("commin_long_ways")
    after = Path("output/commin_long_ways/timing.json").read_bytes()
    assert result["shadow_only"] is True
    assert result["non_target_timing_changes"] == 0
    assert before == after
    assert result["section_map"]
    assert result["edge_diagnostics"]
