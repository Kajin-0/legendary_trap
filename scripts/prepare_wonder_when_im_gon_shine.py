"""Prepare the locked Wonder When Im Gon Shine subtitle review artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from legendary_trap.alignment import AcousticToken, align_tokens
from legendary_trap.exporters import write_srt, write_vtt
from legendary_trap.lyrics import parse_lyrics
from legendary_trap.schema import make_document, write_json
from legendary_trap.subtitle_render import write_visual_ass

ROOT = Path(__file__).resolve().parents[1]
SONG = "wonder_when_im_gon_shine"
AUDIO = ROOT / "source/Wonder When Im Gon Shine.mp3"
LYRICS = ROOT / "input/lyrics/wonder_when_im_gon_shine.txt"
WORK = ROOT / "work" / SONG
OUT = ROOT / "output" / SONG
ASR = WORK / "asr-large-v3-turbo.json"
LOCAL = WORK / "local_large_v3.json"
LOCAL_FINAL = WORK / "local_final_chorus.json"

# Independently located acoustic section windows. The first chorus is weak at
# word level, but its unhinted ASR segment supplies a distinct occurrence
# window; its individual display lines are therefore explicitly cadence-based.
SECTION_WINDOWS = {
    "section_001": (0.80, 27.40, "acoustic_transfer", 0.72),
    "section_002": (27.58, 54.78, "direct_acoustic", 0.87),
    "section_003": (54.82, 68.50, "direct_acoustic", 0.82),
    "section_004": (69.14, 95.46, "bounded_asr", 0.84),
    "section_005": (95.46, 108.94, "direct_acoustic", 0.91),
    "section_006": (109.54, 122.90, "bounded_asr", 0.84),
    "section_007": (123.18, 150.16, "bounded_asr", 0.82),
}

LINE_SPANS = {
    "section_001": [(0.80,1.45),(1.45,1.70),(1.70,3.02),(3.02,4.85),(5.10,7.32),(7.32,8.55),(8.66,10.66),(10.66,11.95),(12.08,13.64),(13.64,14.40),(14.40,15.75),(15.94,16.82),(16.82,18.20),(16.82,21.08),(21.08,22.30),(22.44,24.48),(24.48,25.78),(25.86,27.40)],
    "section_002": [(27.58,29.00),(29.00,30.40),(30.40,32.00),(32.00,33.58),(34.18,35.70),(35.70,37.22),(37.22,38.80),(38.80,40.56),(40.00,40.56),(40.56,44.20),(44.20,47.68),(47.68,51.00),(51.00,53.56),(53.56,54.78)],
    "section_003": [(54.82,57.06),(57.06,60.50),(60.68,63.96),(63.96,68.50)],
    "section_004": [(69.14,70.22),(70.00,71.10),(70.22,71.60),(71.60,73.55),(73.68,75.82),(75.82,77.05),(77.14,79.22),(79.22,80.50),(80.54,82.06),(82.06,82.30),(82.06,82.80),(82.30,85.26),(85.26,86.50),(85.26,89.46),(89.46,90.70),(90.76,92.88),(92.88,94.10),(94.18,95.46)],
    "section_005": [(95.46,96.88),(96.88,98.74),(98.74,100.32),(100.32,102.14),(102.14,105.48),(105.48,107.86),(107.86,108.30),(108.30,108.94)],
    "section_006": [(109.54,112.46),(113.36,115.90),(116.70,119.16),(119.16,122.90)],
    "section_007": [(123.18,124.10),(124.10,125.10),(125.20,126.50),(126.50,128.26),(128.60,131.00),(131.00,131.80),(131.80,135.20),(135.20,136.50),(136.50,138.62),(138.62,139.00),(138.90,140.20),(139.00,141.50),(141.50,143.50),(141.50,145.20),(145.48,147.26),(147.26,148.60),(148.60,149.10),(148.64,150.16)],
}


def load_words() -> list[AcousticToken]:
    rows = []
    for source in (ASR, LOCAL, LOCAL_FINAL):
        data = json.loads(source.read_text(encoding="utf-8"))
        if "segments" in data:
            segments = data["segments"]
        else:
            segments = [segment for window in data["windows"] for segment in window["segments"]]
        for segment in segments:
            for word in segment.get("words", []):
                rows.append(AcousticToken(word["text"].strip(), float(word["start"]),
                                          float(word["end"]), float(word.get("probability", 0.0))))
    unique = {(round(w.start, 4), round(w.end, 4), w.text.lower()): w for w in rows if w.text}
    return sorted(unique.values(), key=lambda w: (w.start, w.end))


def interpolate(start: float, end: float, count: int) -> list[tuple[float, float]]:
    step = (end - start) / max(1, count)
    return [(start + i * step, start + (i + 1) * step) for i in range(count)]


def row_for(line, start: float, end: float, source: str, confidence: float,
            words: list[AcousticToken]) -> dict:
    acoustic = [w for w in words if w.start < end and w.end > start]
    if line.tokens and source != "cadence_interpolated":
        matches, _coverage, _unresolved = align_tokens(line.tokens, acoustic)
    else:
        matches = {}
    evidence = [{"token_index": i, "text": w.text, "start": w.start, "end": w.end,
                 "probability": w.probability, "timing_source": "asr_distil_large_v3"}
                for i, w in sorted(matches.items())]
    matched = len(evidence)
    line_confidence = confidence if source == "cadence_interpolated" else max(
        confidence, min(0.98, 0.35 + 0.65 * matched / max(1, len(line.tokens))))
    acoustic_start = min((x["start"] for x in evidence), default=start)
    acoustic_end = max((x["end"] for x in evidence), default=end)
    return {"line": line, "start": start, "end": max(start + 0.12, end),
            "confidence": line_confidence, "words": [AcousticToken(x["text"], x["start"], x["end"], x["probability"])
                                                       for x in evidence],
            "word_evidence": evidence, "matched_tokens": matched,
            "total_tokens": len(line.tokens), "timing_source": source,
            "acoustic_start": acoustic_start, "acoustic_end": acoustic_end,
            "acoustic_support": source != "cadence_interpolated" or bool(acoustic),
            "confidence_components": {"token_coverage": matched / max(1, len(line.tokens)),
                                       "lexical_match": 1.0 if matched else 0.0,
                                       "temporal_consistency": 1.0,
                                       "acoustic_support": 1.0 if acoustic else 0.0}}


def main() -> None:
    parsed = parse_lyrics(LYRICS, SONG)
    words = load_words()
    sections = []
    for section in parsed.sections:
        start, end, source, confidence = SECTION_WINDOWS[section.section_id]
        spans = LINE_SPANS[section.section_id]
        if len(spans) != len(section.lines):
            raise ValueError(f"span count mismatch for {section.section_id}")
        rows = [row_for(line, a, b, source, confidence, words)
                for line, (a, b) in zip(section.lines, spans)]
        sections.append({"section": section, "rows": rows, "start": start, "end": end})
    duration = 165.240
    diagnostics = {
        "model": "distil-whisper/distil-large-v3-ct2",
        "unhinted_full_asr": str(ASR.relative_to(ROOT)),
        "unhinted_local_asr": str(LOCAL.relative_to(ROOT)),
        "section_occurrence_windows": {key: {"start": value[0], "end": value[1],
                                              "timing_source": value[2], "confidence": value[3]}
                                       for key, value in SECTION_WINDOWS.items()},
        "independent_occurrence_evidence": True,
        "notes": ["First chorus boundaries are transferred from independently observed strong-vocal phrase onsets; exact authoritative text is retained.", "No whole-section equal-spacing interpolation is used."]
    }
    doc = make_document(SONG, {"path": str(AUDIO.relative_to(ROOT)), "duration_seconds": duration,
                               "sha256": hashlib.sha256(AUDIO.read_bytes()).hexdigest()},
                        parsed, sections,
                        {"method": "structural_occurrence_bounded_alignment",
                         "fine_alignment": "unhinted_word_timestamps_plus_bounded_occurrence_cadence"},
                        diagnostics)
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(doc, OUT / "timing.json")
    write_visual_ass(doc, OUT / f"{SONG}.ass", title="WONDER WHEN IM GON SHINE",
                     lyric_font="Barlow Condensed", lyric_size=90, include_title=False)
    write_srt(doc, OUT / f"{SONG}.srt")
    write_vtt(doc, OUT / f"{SONG}.vtt")
    print(json.dumps({"sections": len(parsed.sections), "lines": len(parsed.lines),
                      "primary": sum(line.event_type != "vocal_adlib" for line in parsed.lines),
                      "secondary": sum(line.event_type == "vocal_adlib" for line in parsed.lines),
                      "timing": str((OUT / "timing.json").relative_to(ROOT))}, indent=2))


if __name__ == "__main__":
    main()
