import hashlib
import json
from pathlib import Path

from legendary_trap.lyrics import parse_lyrics
from legendary_trap.repeat_templates import can_promote_repeat_template
from legendary_trap.visualizer import PALETTE_CYCLE_SECONDS, PRESETS

ROOT = Path(__file__).resolve().parents[1]


def _timing(song: str) -> dict:
    return json.loads((ROOT / "output" / song / "timing.json").read_text())


def _lines(document: dict) -> list[dict]:
    return [line for section in document["sections"] for line in section["lines"]]


def test_focus_first_chorus_has_positive_monotonic_primary_events() -> None:
    doc = _timing("focus")
    chorus = next(s for s in doc["sections"] if s["section_id"] == "section_002")
    lines = chorus["lines"]
    assert all(line["end"] > line["start"] for line in lines)
    assert all(lines[i]["end"] <= lines[i + 1]["start"]
               for i in range(len(lines) - 1))
    assert chorus["start"] >= 12.0 and chorus["end"] <= 35.0


def test_chemistry_late_duplicate_occurrence_is_not_renderable() -> None:
    doc = _timing("we_got_chemistry")
    assert not any(section["section_id"] == "section_007" for section in doc["sections"])
    assert "[outro hook]" not in (ROOT / "input/lyrics/we_got_chemistry.txt").read_text()
    assert can_promote_repeat_template({"lines": [
        {"acoustic_supported": False, "words": [{"acoustic_supported": False}]}
    ]}) is False


def test_authoritative_lyrics_contain_no_asr_generated_wording() -> None:
    parsed = parse_lyrics(ROOT / "input/lyrics/we_got_chemistry.txt", "we_got_chemistry")
    assert all(line.original_text for line in parsed.lines)
    assert all("Park, hot" not in line.original_text for line in parsed.lines)


def test_unaffected_timing_documents_remain_hashed_controls() -> None:
    expected = {
        "apple": "8275d3c4b3aa1b8a9ab3141cc3dc90c5e0abce27b7c4493118a17094899d9b88",
        "chokehold": "45d0b778548f4e49fef4cb5a3a3c3a47301266042f01fe368b7c819dbbbd8c35",
        "commin_long_ways": "3f59eadd57cf6acc28e398a4bbbdb2cc45ddc903aa25094ed3a594b69b432b85",
        "off_the_wave": "a067ae1a3f5cb9094244084c3be0430e803a67c74e223378e3332e265d29081b",
        "slidin": "283f141b9d0bab6433d28b7cc5ffacad6ba2d0db7027689f87e00e2ba1f71524",
        "you_missed_it": "18d088ba77baa50b186948237aeeb93b560a418252300c3b55ab23ed75e5097f",
    }
    for song, digest in expected.items():
        assert hashlib.sha256((ROOT / "output" / song / "timing.json").read_bytes()).hexdigest() == digest


def test_visualizer_configuration_remains_frozen() -> None:
    assert PALETTE_CYCLE_SECONDS == 64.0
    assert PRESETS["trap_polar_350_artistlockup"].visualizer == "trap_sunset_polar_v3"
