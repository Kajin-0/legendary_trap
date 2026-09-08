"""Read-only helpers for Suno provenance discovery.

This module deliberately contains no generation, upload, or authentication logic.
Suno data is timing evidence only; authoritative repository lyrics remain the
textual source of truth.
"""
from __future__ import annotations

import math
import statistics
from collections.abc import Mapping
from itertools import pairwise
from urllib.parse import urlparse

ALLOWED_AUDIO_HOSTS = frozenset({"cdn1.suno.ai", "cdn2.suno.ai", "audiopipe.suno.ai"})


def allowed_audio_url(value: str) -> bool:
    """Accept only HTTPS URLs on the explicitly approved Suno audio hosts."""
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_AUDIO_HOSTS
        and not parsed.username
        and not parsed.password
        and parsed.port in (None, 443)
    )


def _walk(value: object) -> list[Mapping[str, object]]:
    found: list[Mapping[str, object]] = []
    if isinstance(value, Mapping):
        if any(key in value for key in ("id", "clip_id", "song_id")):
            found.append(value)
        for child in value.values():
            found.extend(_walk(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk(child))
    return found


def extract_candidates(payload: object) -> list[dict[str, object]]:
    """Extract clip-like objects without assuming one unstable feed envelope."""
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in _walk(payload):
        clip_id = str(item.get("id") or item.get("clip_id") or item.get("song_id") or "")
        if not clip_id or clip_id in seen:
            continue
        seen.add(clip_id)
        result.append(dict(item))
    return result


def _text(candidate: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = candidate.get(key)
        if isinstance(value, str):
            return value
    return ""


def score_candidate(candidate: Mapping[str, object], title: str, artist: str = "",
                    lyric_phrase: str = "", expected_duration: float | None = None) -> dict[str, object]:
    """Return an explainable identity score; title alone cannot be conclusive."""
    metadata = candidate.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    title_value = _text(candidate, "title") or _text(metadata, "title")
    handle = (_text(candidate, "username", "handle", "user_handle", "display_name")
              or _text(metadata, "username", "handle", "user_handle"))
    lyrics = (_text(candidate, "lyrics", "prompt", "gpt_description_prompt")
              or _text(metadata, "lyrics", "prompt", "gpt_description_prompt"))
    haystack = f"{title_value} {handle} {lyrics}".casefold()
    wanted = f"{title} {artist}".casefold()
    title_match = bool(title and title.casefold() == title_value.casefold())
    artist_match = bool(artist and artist.casefold() in haystack)
    phrase_match = bool(lyric_phrase and lyric_phrase.casefold() in haystack)
    duration_value = candidate.get("duration") or metadata.get("duration")
    try:
        duration = float(duration_value)
    except (TypeError, ValueError):
        duration = None
    duration_delta = abs(duration - expected_duration) if duration is not None and expected_duration else None
    score = (4 if title_match else 0) + (3 if artist_match else 0) + (4 if phrase_match else 0)
    if duration_delta is not None:
        score += 2 if duration_delta <= 1 else 1 if duration_delta <= 5 else 0
    return {"clip_id": str(candidate.get("id") or candidate.get("clip_id") or candidate.get("song_id") or ""),
            "title": title_value, "handle": handle, "score": score,
            "title_exact": title_match, "artist_match": artist_match,
            "lyric_phrase_match": phrase_match, "duration": duration,
            "duration_delta": duration_delta,
            "audio_url": _text(candidate, "audio_url") or _text(metadata, "audio_url"),
            "text_examined": wanted}


def _as_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def summarize_alignment(payload: Mapping[str, object]) -> dict[str, object]:
    """Summarize native alignment safely, without changing lyric text."""
    words = payload.get("aligned_words")
    words = words if isinstance(words, list) else []
    p_align = [_as_float(item.get("p_align")) for item in words if isinstance(item, Mapping)]
    p_align = [value for value in p_align if value is not None]
    success_false = sum(1 for item in words if isinstance(item, Mapping) and item.get("success") is False)
    starts = [_as_float(item.get("start_s")) for item in words if isinstance(item, Mapping)]
    starts = [value for value in starts if value is not None]
    chronology_violations = sum(1 for left, right in pairwise(starts) if right < left)
    return {"aligned_word_count": len(words), "success_false_count": success_false,
            "p_align_count": len(p_align),
            "p_align_min": min(p_align) if p_align else None,
            "p_align_median": statistics.median(p_align) if p_align else None,
            "p_align_max": max(p_align) if p_align else None,
            "hoot_cer": payload.get("hoot_cer"),
            "aligned_lyrics_count": len(payload.get("aligned_lyrics", [])) if isinstance(payload.get("aligned_lyrics"), list) else 0,
            "chronology_violations": chronology_violations}
