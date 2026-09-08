from legendary_trap.suno_discovery import (
    allowed_audio_url,
    extract_candidates,
    score_candidate,
    summarize_alignment,
)


def test_suno_audio_allowlist_rejects_redirect_targets() -> None:
    assert allowed_audio_url("https://cdn1.suno.ai/example.mp3")
    assert not allowed_audio_url("https://example.com/example.mp3")
    assert not allowed_audio_url("https://cdn1.suno.ai@evil.example/x.mp3")


def test_candidate_score_requires_more_than_title_for_strong_identity() -> None:
    scored = score_candidate({"id": "x", "title": "FOCUS"}, "FOCUS", "artist", "rare lyric", 240)
    assert scored["score"] == 4
    assert scored["clip_id"] == "x"


def test_alignment_summary_counts_failure_and_chronology() -> None:
    summary = summarize_alignment({"aligned_words": [
        {"word": "a", "start_s": 2, "success": True, "p_align": .9},
        {"word": "b", "start_s": 1, "success": False, "p_align": .2},
    ], "hoot_cer": .1})
    assert summary["aligned_word_count"] == 2
    assert summary["success_false_count"] == 1
    assert summary["chronology_violations"] == 1


def test_candidate_extraction_deduplicates_nested_feed_items() -> None:
    assert [item["id"] for item in extract_candidates({"feed": [{"content_item": {"id": "x"}}, {"id": "x"}]})] == ["x"]
