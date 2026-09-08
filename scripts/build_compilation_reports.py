"""Validate full-song segments and emit compilation metadata/chapter reports."""
from __future__ import annotations

import json
import re
import subprocess
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEGMENTS = ROOT / "output" / "full_compilation" / "segments"
OUT = ROOT / "output" / "full_compilation"
ORDER = [
    "apple", "chokehold", "commin_long_ways", "focus",
    "off_the_wave", "slidin", "we_got_chemistry", "you_missed_it",
]
NAMES = {
    "apple": "AppLE", "chokehold": "Chokehold", "commin_long_ways": "COMIN LONG WAYS",
    "focus": "FOCUS", "off_the_wave": "Off the Wave", "slidin": "slidin",
    "we_got_chemistry": "we got chemistry", "you_missed_it": "you missed it",
}
ARTISTS = {
    "apple": ("KarmaisMagic", None), "chokehold": ("OppTalk", "assets/artists/opptalk.webp"),
    "commin_long_ways": ("PRODBYAPKIMZ", "assets/artists/prodbyapkimz.webp"),
    "focus": ("PRODBYAPKIMZ", "assets/artists/prodbyapkimz.webp"),
    "off_the_wave": ("WILLZ", None), "slidin": ("jayc3", "assets/artists/jayc3.jpeg"),
    "we_got_chemistry": ("VonKai", "assets/artists/vonkaikills.jpeg"),
    "you_missed_it": ("TheSideQuest24", "assets/artists/thesidequest24.webp"),
}


def ass_time(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def segment_info(song_id: str, index: int) -> dict:
    timing = json.loads((ROOT / "output" / song_id / "timing.json").read_text(encoding="utf-8"))
    expected = []
    for section in timing.get("sections", []):
        for line in section.get("lines", []):
            start, end = float(line["start"]), float(line["end"])
            if end > start and end > 0:
                expected.append({"start": max(0.0, start), "end": end,
                                 "text": line["original_text"]})
    ass_path = SEGMENTS / f"{song_id.replace('_', ' ')}.ass"
    rendered = []
    for raw in ass_path.read_text(encoding="utf-8").splitlines():
        if ",Lyric,," not in raw:
            continue
        fields = raw.split(",", 9)
        text = re.sub(r"^\{.*?\}", "", fields[9])
        rendered.append({"start": ass_time(fields[1]), "end": ass_time(fields[2]), "text": text})
    missing = max(0, len(expected) - len(rendered))
    duplicates = max(0, len(rendered) - len(expected))
    retimed = 0
    text_changed = 0
    for expected_line, actual_line in zip(expected, rendered):
        if abs(expected_line["start"] - actual_line["start"]) > 0.011 or abs(expected_line["end"] - actual_line["end"]) > 0.011:
            retimed += 1
        if expected_line["text"] != actual_line["text"]:
            text_changed += 1
    audio_duration = float(timing.get("audio", {}).get("duration_seconds", 0.0))
    segment_path = SEGMENTS / f"{index:02d}_{song_id}.mp4"
    probe = subprocess.run([
        str(ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffprobe"), "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,width,height,avg_frame_rate",
        "-of", "json", str(segment_path),
    ], check=True, capture_output=True, text=True, timeout=30)
    probe_data = json.loads(probe.stdout)
    streams = probe_data.get("streams", [])
    rendered_duration = float(probe_data["format"]["duration"])
    return {
        "song_id": song_id, "title": NAMES[song_id], "artist": ARTISTS[song_id][0],
        "pfp": ARTISTS[song_id][1], "text_only": ARTISTS[song_id][1] is None,
        "source_duration": audio_duration, "rendered_segment_duration": rendered_duration,
        "segment_path": str(segment_path.relative_to(ROOT)), "subtitle_event_count": len(rendered),
        "subtitle_parity": {"canonical_positive_duration": len(expected), "rendered": len(rendered),
                             "missing": missing, "duplicate": duplicates, "retimed": retimed,
                             "text_changed": text_changed},
        "video_stream": next((s for s in streams if s.get("codec_type") == "video"), {}),
        "audio_stream": next((s for s in streams if s.get("codec_type") == "audio"), {}),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    segment_rows = [segment_info(song_id, index) for index, song_id in enumerate(ORDER, 1)]
    gaps = []
    for song_id in ORDER:
        timing = json.loads((ROOT / "output" / song_id / "timing.json").read_text(encoding="utf-8"))
        lines = sorted((line for section in timing.get("sections", []) for line in section.get("lines", [])
                        if float(line["end"]) > float(line["start"])), key=lambda line: float(line["start"]))
        for previous, current in pairwise(lines):
            gap = float(current["start"]) - float(previous["end"])
            if gap > 4.0:
                gaps.append({"song": song_id, "start": float(previous["end"]),
                             "end": float(current["start"]), "length": gap})
    manifest = {"schema_version": 1, "transition_seconds": 0.0,
                "track_order": ORDER, "tracks": segment_rows}
    offset = 0.0
    chapters = []
    for row in segment_rows:
        row["master_start_time"] = round(offset, 3)
        chapters.append(f"{int(offset // 60):02d}:{int(offset % 60):02d} {row['title']} — {row['artist']}")
        offset += row["rendered_segment_duration"]
    master = OUT / "legendary_trap_full_artist_review_v1.mp4"
    if master.exists():
        probe = subprocess.run([
            str(ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffprobe"), "-v", "error",
            "-show_entries", "format=duration:stream=codec_name,codec_type,width,height,avg_frame_rate",
            "-of", "json", str(master),
        ], check=True, capture_output=True, text=True, timeout=30)
        master_data = json.loads(probe.stdout)
        manifest["final_master"] = {"path": str(master.relative_to(ROOT)),
                                    "duration": float(master_data["format"]["duration"]),
                                    "streams": master_data.get("streams", [])}
    else:
        manifest["final_master"] = {"path": str(master.relative_to(ROOT)),
                                    "duration": round(offset, 3), "streams": []}
    (OUT / "canonical_long_gaps.json").write_text(json.dumps(gaps, indent=2) + "\n", encoding="utf-8")
    (OUT / "full_compilation_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (OUT / "youtube_chapters.txt").write_text("\n".join(chapters) + "\n", encoding="utf-8")
    concat = "\n".join(f"file '{(SEGMENTS / f'{index:02d}_{song_id}.mp4').as_posix()}'" for index, song_id in enumerate(ORDER, 1)) + "\n"
    (OUT / "segments.txt").write_text(concat, encoding="utf-8")
    print(json.dumps({"tracks": segment_rows, "gaps": gaps, "chapters": chapters}, indent=2))


if __name__ == "__main__":
    main()
