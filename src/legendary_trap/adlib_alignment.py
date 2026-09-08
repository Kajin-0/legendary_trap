"""Small, bounded alignment helpers for known vocal-adlib events.

This module never changes authoritative display text.  It only compares local
ASR evidence with the parser's acoustic matching view for secondary-lane vocal
events.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

ADLIB_ALIASES: dict[str, set[str]] = {
    "ding": {"ding", "thing"},
    "phew": {"phew", "few", "pew", "whew"},
    "skrrt": {"skrrt", "skrr", "skirt", "skert"},
    "luh": {"luh", "uh", "love", "little"},
    "yeah": {"yeah", "yah", "yea"},
    "woah": {"woah", "whoa", "wow"},
    "what": {"what", "wha"},
}


def normalized_word(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def lexical_similarity(expected: str, observed: str) -> float:
    expected = normalized_word(expected)
    observed = normalized_word(observed)
    if not expected or not observed:
        return 0.0
    if observed in ADLIB_ALIASES.get(expected, {expected}):
        return 1.0
    return SequenceMatcher(None, expected, observed).ratio()


def _candidate_score(expected: str, candidate: dict[str, Any]) -> float:
    similarity = lexical_similarity(expected, str(candidate.get("text", "")))
    probability = float(candidate.get("probability", 0.0) or 0.0)
    return 0.72 * similarity + 0.28 * max(0.0, min(1.0, probability))


def align_adlib_events(events: list[dict[str, Any]], candidates: list[dict[str, Any]],
                       start: float, end: float, min_score: float = 0.62) -> list[dict[str, Any]]:
    """Match ordered vocal events to local ASR candidates monotonically.

    A candidate is consumed at most once.  Unmatched authoritative events are
    returned explicitly rather than being assigned fabricated acoustic support.
    """
    local = [c for c in candidates if start <= float(c.get("start", -1)) < end]
    cursor = 0
    result: list[dict[str, Any]] = []
    for event in events:
        expected_tokens = list(event.get("acoustic_match_tokens") or [])
        matched: list[dict[str, Any]] = []
        event_start = float(event.get("start", start) if event.get("start") is not None else start)
        event_end = float(event.get("end", end) if event.get("end") is not None else end)
        for expected in expected_tokens:
            best_index = None
            best_score = 0.0
            for index in range(cursor, len(local)):
                if not (event_start <= float(local[index].get("start", -1)) <= event_end):
                    continue
                score = _candidate_score(expected, local[index])
                if score > best_score:
                    best_score, best_index = score, index
            if best_index is not None and best_score >= min_score:
                matched.append({"expected": expected, "candidate": local[best_index],
                                "score": round(best_score, 4)})
                cursor = best_index + 1
        if matched:
            first = matched[0]["candidate"]
            last = matched[-1]["candidate"]
            confidence = sum(item["score"] for item in matched) / len(matched)
            result.append({"event_id": event["event_id"], "display_text": event["display_text"],
                           "acoustic_match_tokens": expected_tokens, "start": float(first["start"]),
                           "end": float(last.get("end", last["start"])),
                           "matched": matched, "confidence": round(confidence, 4),
                           "timing_source": "adlib_asr_direct"})
        else:
            result.append({"event_id": event["event_id"], "display_text": event["display_text"],
                           "acoustic_match_tokens": expected_tokens, "matched": [],
                           "confidence": 0.0, "timing_source": "adlib_estimated"})
    return result


def candidate_words(asr_documents: list[dict[str, Any]], start: float, end: float) -> list[dict[str, Any]]:
    """Flatten word evidence from multiple local ASR hypotheses."""
    words: list[dict[str, Any]] = []
    for document in asr_documents:
        model = document.get("model", "unknown")
        for segment in document.get("segments", []):
            for word in segment.get("words", []):
                word_start = float(word.get("start", segment.get("start", 0.0)))
                word_end = float(word.get("end", word_start))
                if start <= word_start < end:
                    words.append({"text": word.get("word", word.get("text", "")).strip(), "start": word_start,
                                  "end": word_end, "probability": word.get("probability", 0.0),
                                  "model": model})
    return sorted(words, key=lambda x: (x["start"], x["end"]))
