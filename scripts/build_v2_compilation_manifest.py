"""Build v2 manifest, long-gap report, chapters, and concat list from segments."""
from __future__ import annotations

import json
import re
import subprocess
from itertools import pairwise
from pathlib import Path

from legendary_trap.compilation import build_track_plan, load_catalog

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "full_compilation_v2"
SEGMENTS = OUT / "segments"
ORDER = load_catalog()[0]["track_order"]
ARTISTS = {
    "apple": ("KarmaisMagic", None), "chokehold": ("OppTalk", "assets/artists/opptalk.webp"),
    "commin_long_ways": ("PRODBYAPKIMZ", "assets/artists/prodbyapkimz.webp"),
    "focus": ("PRODBYAPKIMZ", "assets/artists/prodbyapkimz.webp"),
    "off_the_wave": ("WILLZ", None), "slidin": ("jayc3", "assets/artists/jayc3.jpeg"),
    "we_got_chemistry": ("VonKai", "assets/artists/vonkaikills.jpeg"),
    "you_missed_it": ("TheSideQuest24", "assets/artists/thesidequest24.webp"),
}


def probe(path: Path) -> dict:
    ffprobe = ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffprobe"
    result = subprocess.run([str(ffprobe), "-v", "error", "-show_entries",
                             "format=duration:stream=codec_name,codec_type,width,height,avg_frame_rate",
                             "-of", "json", str(path)], check=True, capture_output=True,
                            text=True, timeout=30)
    return json.loads(result.stdout)


def timing_lines(song: str) -> list[dict]:
    data = json.loads((ROOT / "output" / song / "timing.json").read_text(encoding="utf-8"))
    return sorted([line for section in data.get("sections", []) for line in section.get("lines", [])
                   if float(line["end"]) > float(line["start"])], key=lambda x: float(x["start"]))


def ass_time(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def rendered_subtitles(song: str) -> list[dict]:
    ass = SEGMENTS / f"{song.replace('_', ' ')}.ass"
    rows = []
    for raw in ass.read_text(encoding="utf-8").splitlines():
        if not raw.startswith("Dialogue:"):
            continue
        fields = raw.split(",", 9)
        if fields[3] not in {"Lyric", "Adlib"}:
            continue
        text = re.sub(r"^\{.*?\}", "", fields[9])
        rows.append({"start": ass_time(fields[1]), "end": ass_time(fields[2]),
                     "style": fields[3], "text": text})
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    durations = {song: float(probe(SEGMENTS / f"{index:02d}_{song}.mp4")["format"]["duration"])
                 for index, song in enumerate(ORDER, 1)}
    plans = build_track_plan(durations, transition_seconds=0.0)
    chapters = []
    tracks = []
    gaps = []
    for plan in plans:
        index = ORDER.index(plan.song_id) + 1
        path = SEGMENTS / f"{index:02d}_{plan.song_id}.mp4"
        p = probe(path)
        timing = json.loads((ROOT / "output" / plan.song_id / "timing.json").read_text())
        expected_rows = timing_lines(plan.song_id)
        rendered = rendered_subtitles(plan.song_id)
        expected = len(expected_rows)
        missing = max(0, expected - len(rendered))
        duplicate = max(0, len(rendered) - expected)
        retimed = 0
        text_changed = 0
        for expected_line, actual_line in zip(expected_rows, rendered):
            if (abs(float(expected_line["start"]) - actual_line["start"]) > 0.011 or
                    abs(float(expected_line["end"]) - actual_line["end"]) > 0.011):
                retimed += 1
            if expected_line["original_text"] != actual_line["text"]:
                text_changed += 1
        artist, pfp = ARTISTS[plan.song_id]
        tracks.append({"song_id": plan.song_id, "title": plan.title, "artist": artist, "pfp": pfp,
                       "source_duration": timing["audio"]["duration_seconds"],
                       "rendered_segment_duration": durations[plan.song_id],
                       "master_start_time": plan.master_start,
                       "segment_path": str(path.relative_to(ROOT)), "subtitle_event_count": expected,
                       "subtitle_parity": {"canonical_positive_duration": expected,
                                           "rendered_events": len(rendered), "missing": missing,
                                           "duplicate": duplicate, "retimed": retimed,
                                           "text_changed": text_changed,
                                           "rendered_primary": sum(row["style"] == "Lyric" for row in rendered),
                                           "rendered_secondary": sum(row["style"] == "Adlib" for row in rendered)},
                       "streams": p.get("streams", [])})
        chapters.append(f"{int(plan.master_start // 60):02d}:{int(plan.master_start % 60):02d} {plan.title} — {artist}")
        for a, b in pairwise(timing_lines(plan.song_id)):
            gap = float(b["start"]) - float(a["end"])
            if gap > 4.0:
                gaps.append({"song": plan.song_id, "start": float(a["end"]),
                             "end": float(b["start"]), "length": gap})
    final = OUT / "legendary_trap_full_artist_review_v2.mp4"
    final_probe = probe(final) if final.exists() else {"format": {"duration": sum(durations.values())}, "streams": []}
    manifest = {"schema_version": 2, "transition_seconds": 0.0, "track_order": ORDER,
                "tracks": tracks, "final_master": {"path": str(final.relative_to(ROOT)),
                "duration": float(final_probe["format"]["duration"]), "streams": final_probe.get("streams", [])},
                "final_fade": {"duration_seconds": 3.0,
                               "segment_local_start": round(durations["you_missed_it"] - 3.0, 3),
                               "master_start": round(plans[-1].master_start + durations["you_missed_it"] - 3.0, 3)}}
    (OUT / "full_compilation_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (OUT / "canonical_long_gaps.json").write_text(json.dumps(gaps, indent=2) + "\n")
    (OUT / "youtube_chapters_v2.txt").write_text("\n".join(chapters) + "\n")
    concat = "\n".join(f"file '{(SEGMENTS / f'{i:02d}_{song}.mp4').as_posix()}'" for i, song in enumerate(ORDER, 1)) + "\n"
    (OUT / "segments.txt").write_text(concat)
    print(json.dumps({"tracks": tracks, "gaps": gaps, "chapters": chapters, "manifest": str((OUT / 'full_compilation_manifest.json').relative_to(ROOT))}, indent=2))


if __name__ == "__main__":
    main()
