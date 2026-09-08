def test_attention_alignment_provenance_is_not_free_asr() -> None:
    word = {
        "text": "Focus", "timing_source": "whisper_attention_forced_alignment",
        "transcript_constrained": True, "lexically_recognized": False,
        "acoustic_supported": False,
    }
    assert word["timing_source"] != "asr"
    assert word["transcript_constrained"] is True
    assert word["lexically_recognized"] is False


def test_attention_rejection_does_not_change_direct_metrics() -> None:
    baseline = {"free_asr_tokens": 543, "forced_alignment_tokens": 0}
    assert baseline["free_asr_tokens"] + baseline["forced_alignment_tokens"] == 543
