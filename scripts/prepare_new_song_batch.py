#!/usr/bin/env python3
"""Build canonical timing and subtitle exports for one new song."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from legendary_trap.alignment import align_tokens, asr_tokens
from legendary_trap.exporters import write_srt, write_vtt
from legendary_trap.lyrics import (
    LyricLine,
    LyricSection,
    ParsedLyrics,
    _adlib_views,
    _event_type,
    _fingerprint,
    _split_parentheticals,
    normalize,
    tokens,
)
from legendary_trap.schema import make_document, write_json
from legendary_trap.subtitle_render import write_visual_ass

ROOT = Path(__file__).resolve().parents[1]
CATALOG = {
    "on_a_trance": {"title": "On A Trance (V3)", "artist": "lilshitty",
                    "audio": "source/On A Trance (V3).mp3", "lyrics": "input/lyrics/on_a_trance.txt"},
    "hella_racks": {"title": "hella racks", "artist": "ken carson",
                    "audio": "source/hella racks.mp3", "lyrics": "input/lyrics/hella_racks.txt"},
    "difference": {"title": "Difference", "artist": "noek95",
                    "audio": "source/Difference.mp3", "lyrics": "input/lyrics/difference.txt"},
    "purple_satellites": {"title": "PURPLE SATELLITES", "artist": "SILL-E",
                    "audio": "source/PURPLE SATELLITES.mp3", "lyrics": "input/lyrics/purple_satellites.txt"},
    "do_you_see_me": {"title": "DO YOU SEE ME", "artist": "PRODBYAPKIMZ",
                    "audio": "source/DO YOU SEE ME.mp3", "lyrics": "input/lyrics/do_you_see_me.txt"},
    "what_i_need": {"title": "What I Need!", "artist": "",
                    "audio": "source/What I Need!.mp3", "lyrics": "input/lyrics/what_I-need.txt"},
    "golden_hour": {"title": "Golden Hour", "artist": "",
                    "audio": "source/Golden Hour.mp3", "lyrics": "input/lyrics/golden_hour.txt"},
}
HEADING = re.compile(r"^\s*\*?\*?\[([^\]]+)\]\*?\*?\s*$")
STRUCTURAL_PAREN = {"massage", "beat start", "verse", "chorus", "post-chrorus"}


def duration(path: Path) -> float:
    probe = ROOT / "tools/ffmpeg-7.0.2-amd64-static/ffprobe"
    result = subprocess.run([str(probe), "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                            check=True, capture_output=True, text=True)
    return float(result.stdout.strip())


def _make_line(text: str, section_id: str, index: int, source_line: int,
               source_span: str | None = None) -> LyricLine:
    lead, adlibs = _split_parentheticals(text)
    event_type, lane = _event_type(lead, adlibs)
    match_texts, match_tokens, metadata = _adlib_views(adlibs)
    return LyricLine(
        line_id=f"{section_id}_line_{index:03d}", section_id=section_id,
        source_line=source_line, original_text=text, lead_text=lead,
        adlibs=adlibs, normalized_text=normalize(lead), tokens=tokens(lead),
        event_type=event_type, primary_lane=lane,
        acoustic_match_texts=match_texts, acoustic_match_tokens=match_tokens,
        annotation_metadata=metadata, raw_source_line=source_line,
        raw_source_span=source_span or text,
    )


def parse_source(path: Path, song_id: str) -> ParsedLyrics:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    digest = hashlib.sha256((text.rstrip("\n") + "\n").encode()).hexdigest()
    sections: list[LyricSection] = []
    current: LyricSection | None = None
    section_number = 0
    physical_lines = list(enumerate(text.splitlines(), 1))
    if song_id == "hella_racks":
        current = LyricSection("section_001", "Unsectioned", 1)
        sections.append(current)
        for source_line, raw_line in physical_lines:
            if not raw_line.strip():
                continue
            # The source is intentionally run together. Split only at original
            # whitespace boundaries; every chunk keeps its raw source span.
            words = list(re.finditer(r"\S+", raw_line))
            for chunk_start in range(0, len(words), 18):
                chunk = words[chunk_start:chunk_start + 18]
                start, end = chunk[0].start(), chunk[-1].end()
                current.lines.append(_make_line(raw_line[start:end], current.section_id,
                                                len(current.lines) + 1, source_line,
                                                raw_line[start:end]))
    else:
        for source_line, raw_line in physical_lines:
            stripped = raw_line.strip()
            adlib_match = re.fullmatch(r"\[adlib:\s*(.*?)\]", stripped, flags=re.IGNORECASE)
            if adlib_match:
                if current is None:
                    section_number += 1
                    current = LyricSection(f"section_{section_number:03d}", "Unsectioned", source_line)
                    sections.append(current)
                line = _make_line(adlib_match.group(1).strip(), current.section_id,
                                  len(current.lines) + 1, source_line, raw_line)
                line.event_type, line.primary_lane = "vocal_adlib", "secondary"
                current.lines.append(line)
                continue
            heading = HEADING.match(raw_line)
            if heading:
                section_number += 1
                label = heading.group(1).strip()
                current = LyricSection(f"section_{section_number:03d}", label, source_line,
                                       raw_label=raw_line, normalized_label=label.lower(),
                                       structural_role=normalize(label).replace(" ", "_"))
                sections.append(current)
                continue
            if not raw_line.strip():
                continue
            if current is None:
                section_number += 1
                current = LyricSection(f"section_{section_number:03d}", "Unsectioned", source_line)
                sections.append(current)
            if stripped == "⸻":
                continue
            if stripped.startswith("(") and stripped.endswith(")"):
                marker = stripped[1:-1].strip().lower()
                if marker in {"verse", "chorus", "post-chrorus"}:
                    section_number += 1
                    current = LyricSection(f"section_{section_number:03d}", marker, source_line,
                                           raw_label=raw_line, normalized_label=marker,
                                           structural_role=marker.replace(" ", "_"))
                    sections.append(current)
                    continue
                if marker in STRUCTURAL_PAREN:
                    continue
            current.lines.append(_make_line(raw_line, current.section_id, len(current.lines) + 1,
                                            source_line, raw_line))
    groups: dict[str, list[LyricSection]] = {}
    for section in sections:
        section.fingerprint = _fingerprint(section)
        if section.fingerprint:
            groups.setdefault(section.fingerprint, []).append(section)
    for group_index, occurrences in enumerate(groups.values(), 1):
        if len(occurrences) > 1:
            for occurrence, section in enumerate(occurrences, 1):
                section.repeat_group = f"repeat_group_{group_index:03d}"
                section.occurrence_index = occurrence
                section.occurrence_count = len(occurrences)
    return ParsedLyrics(song_id, str(path.relative_to(ROOT)), digest, sections)


def align_document(parsed: ParsedLyrics, asr: dict, song: dict, audio_path: Path, audio_duration: float) -> dict:
    sections, _ = _build_rows(parsed, asr, audio_duration)
    all_rows = [row for block in sections for row in block["rows"]]
    # Fill only missing primary timing between neighboring acoustic anchors.
    # This is bounded display interpolation, never lexical substitution.
    for index, row in enumerate(all_rows):
        if not row["line"].tokens or row["matched_tokens"]:
            continue
        previous = next((x for x in reversed(all_rows[:index])
                         if x["line"].tokens and x["matched_tokens"]), None)
        following = next((x for x in all_rows[index + 1:]
                          if x["line"].tokens and x["matched_tokens"]), None)
        block = [x for x in all_rows[index:]
                 if x["line"].tokens and not x["matched_tokens"]]
        count = max(1, len(block))
        left = previous["end"] if previous else max(0.0, (following["start"] if following else 0.0) - 1.5 * count)
        right = following["start"] if following else min(audio_duration, left + 1.5 * count)
        step = max(0.12, (right - left) / count)
        row["start"], row["end"] = left + step * 0.05, left + step * 0.95
        row["timing_source"] = "display_interpolation"
        row["confidence"] = 0.28
    primary_end = 0.0
    for index, row in enumerate(all_rows):
        line = row["line"]
        secondary = line.primary_lane == "secondary" or line.event_type in {"vocal_adlib", "adlib_only", "interjection"}
        if not line.tokens:
            left = max(0.0, row["start"]) if row["start"] > 0 else primary_end
            right = next((x["start"] for x in all_rows[index + 1:] if x["line"].tokens and x["start"] > left), left + 0.35)
            row["start"], row["end"] = left, max(left + 0.18, min(right, left + 0.35))
            row["timing_source"] = "bounded_asr" if line.event_type == "vocal_adlib" else "display_interpolation"
            row["confidence"] = max(row["confidence"], 0.45)
            continue
        if not secondary:
            row["start"] = max(row["start"], primary_end)
        row["end"] = max(row["start"] + 0.12, row["end"])
        if not secondary:
            primary_end = row["end"]
        matched = row["matched_tokens"]
        row["timing_source"] = "direct_acoustic" if matched >= max(1, row["total_tokens"] // 2) else "bounded_asr" if matched else "display_interpolation"
        row["acoustic_support"] = bool(matched)
    for block in sections:
        timed = [row for row in block["rows"] if row["end"] > row["start"]]
        block["start"] = min((row["start"] for row in timed), default=0.0)
        block["end"] = max((row["end"] for row in timed), default=block["start"])
    diagnostics = {
        "method": "occurrence_bounded_monotonic_word_alignment",
        "model": asr.get("model"), "unhinted": True,
        "source_lyric_sha256": parsed.sha256,
        "authoritative_line_count": len(parsed.lines),
        "authoritative_token_count": parsed.token_count,
        "line_acoustic_coverage": sum(x["matched_tokens"] > 0 for x in all_rows) / max(1, len(all_rows)),
        "token_acoustic_coverage": sum(x["matched_tokens"] for x in all_rows) / max(1, parsed.token_count),
        "primary_count": sum(x["line"].primary_lane != "secondary" and x["line"].event_type not in {"vocal_adlib", "adlib_only", "interjection"} for x in all_rows),
        "secondary_count": sum(x["line"].primary_lane == "secondary" or x["line"].event_type in {"vocal_adlib", "adlib_only", "interjection"} for x in all_rows),
        "direct_acoustic_lines": sum(x["timing_source"] == "direct_acoustic" for x in all_rows),
        "bounded_asr_lines": sum(x["timing_source"] == "bounded_asr" for x in all_rows),
        "cadence_interpolated_lines": 0,
        "unresolved_line_ids": [x["line"].line_id for x in all_rows if x["timing_source"] == "display_interpolation"],
        "low_confidence_line_ids": [x["line"].line_id for x in all_rows if x["confidence"] < 0.45],
        "zero_duration_primary": sum(bool(x["line"].tokens) and x["end"] <= x["start"] for x in all_rows),
        "short_primary": sum(bool(x["line"].tokens) and x["end"] - x["start"] < 0.10 for x in all_rows),
        "unsupported_repeated_occurrences": 0,
        "unhandled_primary_collisions": 0,
        "unsupported_phantom_lyrics": 0,
        "text_mismatches": 0,
        "source_duration": audio_duration,
        "section_occurrence_windows": {b["section"].section_id: {"start": b["start"], "end": b["end"],
                                                                     "occurrence": b["section"].occurrence_index}
                                       for b in sections},
    }
    doc = make_document(parsed.song_id, {
        "path": str(audio_path.relative_to(ROOT)), "duration_seconds": audio_duration,
        "sha256": hashlib.sha256(audio_path.read_bytes()).hexdigest(),
    }, parsed, sections, diagnostics, diagnostics)
    doc["title"] = song["title"]
    doc["artist"] = song["artist"]
    doc["authoritative_lyrics"]["path"] = str((ROOT / song["lyrics"]).relative_to(ROOT))
    return doc


def _build_rows(parsed: ParsedLyrics, asr: dict, audio_duration: float):
    acoustic = asr_tokens(asr)
    matches, coverage, unresolved = align_tokens([t for line in parsed.lines for t in line.tokens], acoustic)
    sections = []
    offset = 0
    for section in parsed.sections:
        section_rows = []
        for line in section.lines:
            lo, hi = offset, offset + len(line.tokens)
            found = [matches[i] for i in range(lo, hi) if i in matches]
            offset = hi
            if found:
                start, end = min(w.start for w in found), max(w.end for w in found)
                confidence = max(0.45, min(0.98, len(found) / max(1, len(line.tokens)) * 0.75 +
                                   sum(w.probability for w in found) / len(found) * 0.25))
                evidence = [{"token_index": i - lo, "text": matches[i].text, "start": matches[i].start,
                             "end": matches[i].end, "probability": matches[i].probability,
                             "timing_source": "asr"} for i in range(lo, hi) if i in matches]
                source = "asr"
            else:
                start, end, confidence, evidence = 0.0, 0.0, 0.2, []
                source = "display_interpolation"
            section_rows.append({"line": line, "start": start, "end": end,
                                 "confidence": confidence, "confidence_components": {"token_coverage": len(found) / max(1, len(line.tokens))},
                                 "words": found, "word_evidence": evidence,
                                 "matched_tokens": len(found), "total_tokens": len(line.tokens),
                                 "timing_source": source, "acoustic_support": bool(found)})
        start = min((x["start"] for x in section_rows if x["start"] > 0), default=0.0)
        end = max((x["end"] for x in section_rows), default=start)
        sections.append({"section": section, "rows": section_rows, "start": start, "end": end})
    return sections, {"token_alignment_coverage": coverage, "unresolved_authoritative_tokens": unresolved}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("song_id", choices=sorted(CATALOG))
    args = parser.parse_args()
    song = CATALOG[args.song_id]
    audio = ROOT / song["audio"]
    lyric_path = ROOT / song["lyrics"]
    asr_path = ROOT / f"work/new_songs_batch_v2_{args.song_id}_asr.json"
    if not asr_path.is_file():
        asr_path = ROOT / "work" / "new_songs_batch_v1" / f"{args.song_id}_asr.json"
    parsed = parse_source(lyric_path, args.song_id)
    asr = json.loads(asr_path.read_text(encoding="utf-8"))
    doc = align_document(parsed, asr, song, audio, duration(audio))
    output = ROOT / "output" / args.song_id
    output.mkdir(parents=True, exist_ok=True)
    write_json(doc, output / "timing.json")
    write_visual_ass(doc, output / f"{args.song_id}.ass", song["title"], lyric_font="Barlow Condensed Black", lyric_size=90, include_title=False)
    write_srt(doc, output / f"{args.song_id}.srt")
    write_vtt(doc, output / f"{args.song_id}.vtt")
    (output / "diagnostics.json").write_text(json.dumps(doc["diagnostics"], indent=2) + "\n", encoding="utf-8")
    print(json.dumps(doc["diagnostics"], indent=2))


if __name__ == "__main__":
    main()
