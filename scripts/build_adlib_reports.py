"""Build bounded adlib shadow diagnostics from existing ASR evidence."""
from __future__ import annotations

import json
from pathlib import Path

from legendary_trap.adlib_alignment import align_adlib_events, candidate_words, lexical_similarity
from legendary_trap.lyrics import parse_lyrics

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "adlib_alignment"
SONGS = ["apple", "chokehold", "commin_long_ways", "focus", "off_the_wave", "slidin",
         "we_got_chemistry", "you_missed_it"]


def load_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def sections_for_adlibs(parsed):
    return [s for s in parsed.sections if s.structural_role in {"intro", "outro"}
            or s is parsed.sections[0] or s is parsed.sections[-1]]


def line_rows(song: str, parsed, timing: dict) -> dict:
    return {line["line_id"]: line for section in timing.get("sections", [])
            for line in section.get("lines", [])}


def event_rows(song: str, section, rows: dict) -> list[dict]:
    result = []
    for line in section.lines:
        if line.primary_lane != "secondary" and not line.adlibs:
            continue
        row = rows.get(line.line_id, {})
        for index, match_tokens in enumerate(line.acoustic_match_tokens):
            result.append({"event_id": f"{line.line_id}_adlib_{index + 1}",
                           "line_id": line.line_id, "display_text": line.original_text,
                           "acoustic_match_text": line.acoustic_match_texts[index],
                           "acoustic_match_tokens": match_tokens,
                           "annotation_metadata": line.annotation_metadata[index],
                           "start": row.get("start"), "end": row.get("end"),
                           "timing_source": row.get("timing_source", "unknown"),
                           "estimated": row.get("timing_source") in {"estimated", "line_estimate"}})
    return result


def shadow_song(song: str) -> dict:
    lyric_path = ROOT / "input" / "lyrics" / f"{song}.txt"
    parsed = parse_lyrics(lyric_path, song)
    timing = load_json(ROOT / "output" / song / "timing.json", {})
    rows = line_rows(song, parsed, timing)
    asr = load_json(ROOT / "work" / song / "asr-base.en.json", {})
    sections = sections_for_adlibs(parsed)
    section_results = []
    for section in sections:
        events = event_rows(song, section, rows)
        if not events:
            continue
        lower = min((x["start"] for x in events if x["start"] is not None), default=0.0)
        upper = max((x["end"] for x in events if x["end"] is not None), default=lower)
        candidates = candidate_words([asr], lower, upper)
        aligned = align_adlib_events(events, candidates, lower, upper)
        by_id = {x["event_id"]: x for x in aligned}
        output = []
        for event in events:
            match = by_id[event["event_id"]]
            output.append({**event, "candidate_start": match.get("start"), "candidate_end": match.get("end"),
                           "candidate_confidence": match.get("confidence", 0.0),
                           "candidate_source": match.get("timing_source"),
                           "matched_candidates": match.get("matched", []),
                           "promotion_recommendation": "retain_current"})
        section_results.append({"section_id": section.section_id, "structural_role": section.structural_role,
                                "window": {"start": lower, "end": upper}, "events": output,
                                "candidate_count": len(candidates)})
    if not section_results:
        return {"song": song, "events": [], "promotion_recommendation": "none"}
    return {"song": song, "sections": section_results,
            "models": [asr.get("model", "missing")], "promotion_recommendation": "shadow_only"}


def main() -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    you = shadow_song("you_missed_it")
    intro = next((s for s in you.get("sections", []) if s["section_id"] == "section_001"),
                 {"section_id": "section_001", "events": []})
    (REPORT / "you_missed_it_intro.json").write_text(json.dumps({
        "song": "you_missed_it", "section_id": "section_001", "window": {"start": 0.0, "end": 10.8},
        "events": intro.get("events", []),
        "ding_candidates": [x for x in candidate_words([load_json(ROOT / "work/you_missed_it/asr-base.en.json", {})], 0, 10.8)
                            if lexical_similarity("ding", x["text"]) >= 0.65],
        "distil_hypothesis": {"attempted": True, "status": "aborted_during_model_load",
                              "reason": "bounded process produced no result; no unbounded retry"},
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    outro_section = next((s for s in you.get("sections", []) if s["section_id"] == "section_007"),
                         {"events": []})
    outro = {"song": "you_missed_it", "window": {"start": 153.0, "end": 169.6},
             "events": outro_section.get("events", []),
             "promotion_recommendation": "retain_current_good_outro"}
    (REPORT / "you_missed_it_outro_shadow.json").write_text(json.dumps(outro, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    all_songs = [shadow_song(song) for song in SONGS]
    (REPORT / "all_song_intro_outro_shadow.json").write_text(json.dumps({"songs": all_songs}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    comparison = {"mode": "shadow_only", "authoritative_text_changed": False,
                  "primary_timing_promoted": False, "songs": [{"song": x["song"],
                  "event_count": sum(len(s.get("events", [])) for s in x.get("sections", [])),
                  "candidate_direct_events": sum(bool(e.get("matched_candidates")) for s in x.get("sections", [])
                                                 for e in s.get("events", []))} for x in all_songs],
                  "decision": "retain_current_timing_until_multi-model_adlib_anchor_is_available"}
    (REPORT / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    (REPORT / "README.md").write_text("""# Bounded vocal-adlib shadow alignment\n\nParenthetical vocal events are kept as exact display text and matched through a separate acoustic view. `Ding! bell sound` is treated as the vocal token `ding` with `bell sound` retained as annotation metadata. This report is shadow-only: no speculative adlib candidate was promoted over current production timing.\n\nThe bounded distil-large-v3 intro attempt was aborted during model load without an output; the cached base hypothesis was retained as the reproducible control.\n""", encoding="utf-8")


if __name__ == "__main__":
    main()
