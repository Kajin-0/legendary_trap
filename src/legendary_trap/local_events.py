"""Bounded sparse-event mapping for secondary lyric/ad-lib lanes."""
from __future__ import annotations


def map_sparse_events(events: list[dict], acoustic_segments: list[dict],
                      start: float, end: float) -> list[dict]:
    """Map bounded acoustic segments monotonically, estimating quiet gaps."""
    segments = [segment for segment in acoustic_segments
                if segment.get("end", 0.0) > start and segment.get("start", 0.0) < end]
    cursor = start
    result = []
    for index, event in enumerate(events):
        segment_index = event.get("acoustic_segment_index")
        segment = segments[segment_index] if segment_index is not None and segment_index < len(segments) else None
        if segment:
            event_start = max(cursor, float(segment["start"]))
            event_end = max(event_start + 0.25, min(end, float(segment["end"])))
            source = "asr"
        else:
            next_index = event.get("next_acoustic_segment_index", len(segments))
            next_start = float(segments[next_index]["start"]) if next_index < len(segments) else end
            event_start = cursor
            event_end = max(event_start + 0.25, min(next_start, event_start + 0.9))
            source = "estimated"
        result.append({**event, "start": round(event_start, 3), "end": round(event_end, 3),
                       "timing_source": source, "acoustic_supported": source == "asr"})
        cursor = event_end
    return result
