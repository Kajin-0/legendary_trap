"""Regression coverage for the standalone Wonder subtitle preparation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from legendary_trap.lyrics import parse_lyrics

ROOT = Path(__file__).resolve().parents[1]
SONG = "wonder_when_im_gon_shine"
TIMING = ROOT / "output" / SONG / "timing.json"


def _document() -> dict:
    return json.loads(TIMING.read_text(encoding="utf-8"))


def test_authoritative_wonder_lyrics_and_repeated_occurrences() -> None:
    path = ROOT / "input/lyrics/wonder_when_im_gon_shine.txt"
    parsed = parse_lyrics(path, SONG)
    assert parsed.sha256 == "c6fe5d85cebe8a6ac429da344710d0de3c3211cb036b1f6fbf35d3226e28600e"
    assert [section.occurrence_index for section in parsed.sections if section.label == "chorus"] == [1, 2, 3]
    assert [section.occurrence_index for section in parsed.sections if section.label == "bridge"] == [1, 2]
    assert "wonder when im gon-" in [line.original_text for line in parsed.lines]


def test_wonder_timing_has_exact_authoritative_text_and_no_phantoms() -> None:
    document = _document()
    source = [line["original_text"] for section in document["sections"] for line in section["lines"]]
    authoritative = [line for line in (ROOT / "input/lyrics/wonder_when_im_gon_shine.txt").read_text().splitlines()
                     if line.strip() and not line.startswith("[")]
    assert source == authoritative
    assert document["diagnostics"]["independent_occurrence_evidence"] is True


def test_wonder_structural_invariants() -> None:
    document = _document()
    primary = [line for section in document["sections"] for line in section["lines"]
               if line["event_type"] != "vocal_adlib"]
    assert all(line["end"] > line["start"] for line in primary)
    assert all(line["end"] - line["start"] >= 0.10 for line in primary)
    assert sum(line["event_type"] == "vocal_adlib" for section in document["sections"] for line in section["lines"]) == 25


def test_wonder_subtitle_exports_match_canonical_rows() -> None:
    document = _document()
    expected = [line["original_text"] for section in document["sections"] for line in section["lines"]]
    for extension in ("ass", "srt", "vtt"):
        path = ROOT / "output" / SONG / f"{SONG}.{extension}"
        assert path.exists()
    ass = (ROOT / "output" / SONG / f"{SONG}.ass").read_text()
    assert sum("Dialogue:" in line for line in ass.splitlines()) == len(expected)
    assert all(text in ass for text in expected)


def test_existing_eight_timing_hashes_remain_frozen() -> None:
    expected = {
        "apple": "8275d3c4b3aa1b8a9ab3141cc3dc90c5e0abce27b7c4493118a17094899d9b88",
        "chokehold": "1cc68e6703aa62417e058acd2e723e1739c0efc8b94e39807dc2265a9e698385",
        "commin_long_ways": "3f59eadd57cf6acc28e398a4bbbdb2cc45ddc903aa25094ed3a594b69b432b85",
        "focus": "63435609fc1091fc14947765ce5869dc283e2173c9ee0edb61fdfb4996f1fc8a",
        "off_the_wave": "a067ae1a3f5cb9094244084c3be0430e803a67c74e223378e3332e265d29081b",
        "slidin": "283f141b9d0bab6433d28b7cc5ffacad6ba2d0db7027689f87e00e2ba1f71524",
        "we_got_chemistry": "2719ca38ecfaba9c38c1c397a501b5ebd61a9b1fc82e5a4fcbd31228d1141979",
        "you_missed_it": "18d088ba77baa50b186948237aeeb93b560a418252300c3b55ab23ed75e5097f",
    }
    for song, digest in expected.items():
        assert hashlib.sha256((ROOT / "output" / song / "timing.json").read_bytes()).hexdigest() == digest
