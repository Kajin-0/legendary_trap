"""Evidence-driven weak-line analysis for pilot reports."""
from __future__ import annotations

import json
from pathlib import Path

from rapidfuzz.fuzz import ratio

from .lyrics import normalize


def analyze(song_id: str, timing_path: Path, asr_path: Path, lyrics_path: Path,
            output_json: Path, output_markdown: Path, margin: float = 2.0) -> list[dict]:
    timing = json.loads(timing_path.read_text())
    asr = json.loads(asr_path.read_text())
    asr_words = [w for segment in asr["segments"] for w in segment["words"]]
    rows = [(section, line) for section in timing["sections"] for line in section["lines"]]
    result = []
    for index, (section, line) in enumerate(rows):
        if line["matched_tokens"] == line["total_tokens"] and line["confidence"] >= 0.45:
            continue
        previous = next(((s, l) for s, l in reversed(rows[:index]) if l["matched_tokens"] and l["confidence"] >= 0.45), None)
        following = next(((s, l) for s, l in rows[index + 1:] if l["matched_tokens"] and l["confidence"] >= 0.45), None)
        window_start = max(0.0, (previous[1]["end"] if previous else 0.0) - margin)
        window_end = min(float(timing["audio"]["duration_seconds"]), (following[1]["start"] if following else timing["audio"]["duration_seconds"]) + margin)
        nearby = [w for w in asr_words if w["end"] >= window_start and w["start"] <= window_end]
        nearest = sorted(nearby, key=lambda w: min(abs(w["start"] - line["start"]), abs(w["end"] - line["end"])))[:16]
        lexical = ratio(normalize(line["lead_text"] if "lead_text" in line else line["original_text"],), " ".join(w["text"] for w in nearest)) / 100 if nearest else 0.0
        if line["matched_tokens"] == 0:
            if line["start"] == line["end"] or line["confidence"] <= 0.12:
                failure = "ASR deletion / low vocal SNR / instrumental gap"
            else:
                failure = "ASR deletion or sequence-alignment scoring issue"
        else:
            failure = "partial ASR substitution/deletion"
        result.append({"line_id": line["line_id"], "section_id": section["section_id"],
                       "exact_authoritative_text": line["original_text"], "normalized_text": normalize(line["lead_text"] if "lead_text" in line else line["original_text"]),
                       "current_start": line["start"], "current_end": line["end"], "aligned_tokens": line["matched_tokens"],
                       "authoritative_tokens": line["total_tokens"], "unresolved_tokens": line["total_tokens"] - line["matched_tokens"],
                       "confidence": line["confidence"], "confidence_components": line.get("confidence_components", {}),
                       "lexical_similarity_nearest_asr": lexical,
                       "nearest_asr_words":[{"text":w["text"],"start":w["start"],"end":w["end"],"probability":w.get("probability")} for w in nearest],
                       "preceding_reliable_line": previous[1] if previous else None,
                       "following_reliable_line": following[1] if following else None,
                       "available_temporal_window":{"start":round(window_start,3),"end":round(window_end,3)},
                       "suspected_failure_class": failure})
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps({"song_id":song_id,"rows":result}, indent=2, ensure_ascii=False) + "\n")
    md=[f"# {song_id} failure analysis", "", "Only lines with missing or partial direct ASR token support are listed.", "", "| Line | Match | Confidence | Window | Suspected class |", "|---|---:|---:|---:|---|"]
    for row in result:
        w=row["available_temporal_window"]
        md.append(f"| `{row['line_id']}` {row['exact_authoritative_text']} | {row['aligned_tokens']}/{row['authoritative_tokens']} | {row['confidence']:.2f} | {w['start']:.2f}–{w['end']:.2f} | {row['suspected_failure_class']} |")
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.write_text("\n".join(md) + "\n")
    return result
