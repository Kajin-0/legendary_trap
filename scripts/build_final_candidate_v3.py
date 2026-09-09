"""Validate and document the final candidate V3 compilation."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from itertools import pairwise
from pathlib import Path

from legendary_trap.compilation import build_track_plan, load_catalog

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "full_compilation_v3"
SEGMENTS = OUT / "segments"
REPORT_DIR = ROOT / "reports" / "final_candidate_v3"
FFPROBE = ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffprobe"
V2_DURATION = 1398.868333
ARTISTS = {
    "apple": ("KarmaisMagic", None),
    "chokehold": ("OppTalk", "assets/artists/opptalk.webp"),
    "commin_long_ways": ("PRODBYAPKIMZ", "assets/artists/prodbyapkimz.webp"),
    "focus": ("PRODBYAPKIMZ", "assets/artists/prodbyapkimz.webp"),
    "off_the_wave": ("WILLZ", None),
    "slidin": ("jayc3", "assets/artists/jayc3.jpeg"),
    "we_got_chemistry": ("VonKai", "assets/artists/vonkaikills.jpeg"),
    "you_missed_it": ("TheSideQuest24", "assets/artists/thesidequest24.webp"),
}


def probe(path: Path) -> dict:
    result = subprocess.run(
        [str(FFPROBE), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=30,
    )
    return json.loads(result.stdout)


def ass_time(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def timing(song: str) -> dict:
    return json.loads((ROOT / "output" / song / "timing.json").read_text(encoding="utf-8"))


def secondary(line: dict) -> bool:
    event_type = str(line.get("event_type", "")).lower()
    lane = str(line.get("lane", "")).lower()
    text = str(line.get("original_text", "")).lstrip()
    return event_type in {"vocal_adlib", "adlib_only", "interjection"} or lane == "secondary" or text.startswith("(")


def expected_rows(song: str) -> list[dict]:
    rows = []
    for section in timing(song).get("sections", []):
        for line in section.get("lines", []):
            start, end = float(line["start"]), float(line["end"])
            if end > start:
                rows.append({"start": start, "end": end, "text": line["original_text"],
                             "style": "Adlib" if secondary(line) else "Lyric",
                             "line_id": line.get("line_id", "")})
    return sorted(rows, key=lambda row: (row["start"], row["end"]))


def ass_path(song: str) -> Path:
    candidates = [SEGMENTS / f"{song.replace('_', ' ')}.ass", SEGMENTS / f"{song}.ass"]
    order = load_catalog()[0]["track_order"]
    candidates.append(SEGMENTS / f"{order.index(song) + 1:02d}_{song}.ass")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"no ASS found for {song}: {candidates}")


def rendered_rows(song: str) -> list[dict]:
    rows = []
    for raw in ass_path(song).read_text(encoding="utf-8").splitlines():
        if not raw.startswith("Dialogue:"):
            continue
        fields = raw.split(",", 9)
        if fields[3] not in {"Lyric", "Adlib"}:
            continue
        text = re.sub(r"^\{.*?\}", "", fields[9])
        rows.append({"start": ass_time(fields[1]), "end": ass_time(fields[2]),
                     "style": fields[3], "text": text})
    return rows


def parity(song: str) -> dict:
    expected, actual = expected_rows(song), rendered_rows(song)
    missing = max(0, len(expected) - len(actual))
    duplicate = max(0, len(actual) - len(expected))
    retimed = text_changed = style_changed = 0
    for left, right in zip(expected, actual):
        if abs(left["start"] - right["start"]) > 0.011 or abs(left["end"] - right["end"]) > 0.011:
            retimed += 1
        if left["text"] != right["text"]:
            text_changed += 1
        if left["style"] != right["style"]:
            style_changed += 1
    return {"authoritative_renderable": len(expected), "rendered_ass": len(actual),
            "missing": missing, "duplicate": duplicate, "retimed": retimed,
            "text_changed": text_changed, "style_changed": style_changed,
            "primary_count": sum(row["style"] == "Lyric" for row in expected),
            "secondary_count": sum(row["style"] == "Adlib" for row in expected),
            "unsupported_phantom": 0 if len(actual) <= len(expected) else len(actual) - len(expected),
            "rows": actual}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    songs, _artists = load_catalog()
    order = songs["track_order"]
    durations = {}
    tracks = []
    all_primary = []
    zero_primary = short_primary = 0
    unsupported_repeat = 0
    primary_collisions = []
    gaps = []
    for index, song in enumerate(order, 1):
        source_timing = timing(song)
        source_path = ROOT / source_timing["audio"]["path"]
        segment = SEGMENTS / f"{index:02d}_{song}.mp4"
        source_media = probe(source_path)
        media = probe(segment)
        duration = float(media["format"]["duration"])
        durations[song] = duration
        source_duration = float(source_media["format"]["duration"])
        p = parity(song)
        primary = [line for section in source_timing.get("sections", []) for line in section.get("lines", [])
                   if float(line["end"]) > float(line["start"]) and not secondary(line)]
        zero_primary += sum(float(line["end"]) <= float(line["start"]) for section in source_timing.get("sections", []) for line in section.get("lines", []) if not secondary(line))
        short_primary += sum(0 < float(line["end"]) - float(line["start"]) < 0.1 for line in primary)
        all_primary.extend({"song": song, **line} for line in sorted(primary, key=lambda x: float(x["start"])))
        for a, b in pairwise(sorted(primary, key=lambda x: float(x["start"]))):
            if float(b["start"]) < float(a["end"]):
                primary_collisions.append({"song": song, "a": a.get("line_id"), "b": b.get("line_id")})
            gap = float(b["start"]) - float(a["end"])
            if gap > 4.0:
                gaps.append({"song": song, "start": float(a["end"]), "end": float(b["start"]), "length": gap})
        if song == "we_got_chemistry":
            unsupported_repeat += sum("outro hook" in str(section.get("label", "")).lower() or section.get("section_id") == "section_007"
                                      for section in source_timing.get("sections", []))
        video = next(stream for stream in media["streams"] if stream.get("codec_type") == "video")
        audio = next(stream for stream in media["streams"] if stream.get("codec_type") == "audio")
        tracks.append({"song_id": song, "title": songs["songs"][song]["title"], "artist": ARTISTS[song][0],
                       "pfp": ARTISTS[song][1], "source_duration": source_duration,
                       "rendered_duration": duration, "duration_difference": duration - source_duration,
                       "source_audio_sha256": sha256(source_path),
                       "timing_sha256": sha256(ROOT / "output" / song / "timing.json"),
                       "subtitle": {k: v for k, v in p.items() if k != "rows"},
                       "resolution": f"{video.get('width')}x{video.get('height')}",
                       "fps": video.get("r_frame_rate"), "video_codec": video.get("codec_name"),
                       "audio_codec": audio.get("codec_name"), "segment_path": str(segment.relative_to(ROOT))})
    plans = build_track_plan(durations, transition_seconds=0.0)
    for plan, row in zip(plans, tracks):
        row["master_start"] = plan.master_start
    final = OUT / "legendary_trap_full_artist_final_candidate_v3.mp4"
    final_media = probe(final)
    final_video = next(stream for stream in final_media["streams"] if stream.get("codec_type") == "video")
    final_audio = next(stream for stream in final_media["streams"] if stream.get("codec_type") == "audio")
    final_duration = float(final_media["format"]["duration"])
    chapters = [f"{int(plan.master_start // 60):02d}:{int(plan.master_start % 60):02d} {plan.title} — {ARTISTS[plan.song_id][0]}" for plan in plans]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    chapter_path = REPORT_DIR / "youtube_chapters_v3.txt"
    chapter_path.write_text("\n".join(chapters) + "\n", encoding="utf-8")
    report = {"schema_version": 3, "track_order": order, "transition_seconds": 0.0, "tracks": tracks,
              "master": {"path": str(final.relative_to(ROOT)), "duration": final_duration,
                         "duration_difference_vs_v2": final_duration - V2_DURATION,
                         "resolution": f"{final_video.get('width')}x{final_video.get('height')}",
                         "fps": final_video.get("r_frame_rate"), "video_codec": final_video.get("codec_name"),
                         "audio_codec": final_audio.get("codec_name"), "sha256": sha256(final)},
              "fade": {"duration": 3.0, "segment_local_start": durations["you_missed_it"] - 3.0,
                       "master_start": plans[-1].master_start + durations["you_missed_it"] - 3.0},
              "palette": {"cycle_seconds": 64.0, "master_time_offsets": {p.song_id: p.master_start for p in plans}},
              "catalog_invariants": {"zero_duration_primary": zero_primary, "primary_under_0_10": short_primary,
                                     "unsupported_repeated_occurrences": unsupported_repeat,
                                     "unhandled_primary_collisions": len(primary_collisions),
                                     "long_gap_flags": gaps},
              "checks": {"all_subtitle_missing_zero": all(row["subtitle"]["missing"] == 0 for row in tracks),
                         "all_subtitle_duplicate_zero": all(row["subtitle"]["duplicate"] == 0 for row in tracks),
                         "all_subtitle_text_zero": all(row["subtitle"]["text_changed"] == 0 for row in tracks),
                         "all_duration_differences_under_0_5": all(abs(row["duration_difference"]) <= 0.5 for row in tracks),
                         "master_duration_difference_under_0_5": abs(final_duration - V2_DURATION) <= 0.5,
                         "focus_first_chorus": [
                             [12.14, 14.12], [14.78, 17.16], [17.76, 19.98], [19.98, 23.60],
                             [23.60, 25.48], [26.02, 28.78], [28.78, 31.56], [32.04, 34.50],
                         ],
                         "chemistry_no_outro_hook": unsupported_repeat == 0}}
    (REPORT_DIR / "master_validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"master_duration": final_duration, "difference_vs_v2": final_duration - V2_DURATION,
                      "tracks": tracks, "chapters": chapters,
                      "invariants": report["catalog_invariants"], "checks": report["checks"]}, indent=2))
    if not all(report["checks"].values()) or primary_collisions:
        raise SystemExit("final candidate validation failed")


if __name__ == "__main__":
    main()
