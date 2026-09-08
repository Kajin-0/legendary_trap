from legendary_trap.lyric_timing import complete_estimated_lines, estimated_line_ids


def test_estimated_line_is_bounded_and_marked() -> None:
    doc = {"sections": [{"lines": [
        {"line_id": "a", "start": 1.0, "end": 2.0, "original_text": "A"},
        {"line_id": "weak", "start": 2.0, "end": 2.1, "original_text": "Weak", "words": [{"text": "Weak"}]},
        {"line_id": "b", "start": 4.0, "end": 5.0, "original_text": "B"},
    ]}]}
    out = complete_estimated_lines(doc, 10.0, {"weak"})
    line = out["sections"][0]["lines"][1]
    assert (line["start"], line["end"]) == (2.0, 4.0)
    assert line["timing_source"] == "estimated"
    assert line["acoustic_supported"] is False
    assert estimated_line_ids(out) == ["weak"]


def test_estimated_words_do_not_claim_acoustic_support() -> None:
    doc = {"sections": [{"lines": [
        {"line_id": "a", "start": 1.0, "end": 2.0},
        {"line_id": "weak", "start": 2.0, "end": 2.1, "words": [{"text": "weak"}]},
        {"line_id": "b", "start": 3.0, "end": 4.0},
    ]}]}
    line = complete_estimated_lines(doc, 5.0, {"weak"})["sections"][0]["lines"][1]
    assert line["words"][0]["timing_source"] == "line_estimate"
    assert line["words"][0]["acoustic_supported"] is False
