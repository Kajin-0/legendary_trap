#!/usr/bin/env python3
"""Render bounded previews sequentially and write compact QC reports."""
from __future__ import annotations

import json
import subprocess

from legendary_trap.lyrics import parse_lyrics
from legendary_trap.render import ROOT, render

SONGS = {"apple": 20, "chokehold": 35, "commin_long_ways": 45,
         "off_the_wave": 45, "slidin": 20, "we_got_chemistry": 60, "you_missed_it": 30}


def main() -> int:
    report_dir = ROOT / "reports" / "visualizer_previews"
    report_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "song_manifest.json").read_text(encoding="utf-8"))
    by_id = {song["id"]: song for song in manifest["songs"]}
    summaries = []
    ffprobe = ROOT / "tools/ffmpeg-7.0.2-amd64-static/ffprobe"
    for song_id, start in SONGS.items():
        result = render(song_id, timeout_seconds=240, preview_start=start, preview_duration=25)
        timing = json.loads((ROOT / "output" / "previews" / f"{song_id}.timing.json").read_text())
        source_lines = parse_lyrics(ROOT / by_id[song_id]["lyrics_path"], song_id).lines
        lines = [line for section in timing["sections"] for line in section["lines"]]
        media = subprocess.run([str(ffprobe), "-v", "error", "-show_entries",
                                "format=duration:stream=codec_type,width,height", "-of", "json",
                                result["video"]], cwd=ROOT, check=True, capture_output=True,
                               text=True, timeout=30)
        probe = json.loads(media.stdout)
        streams = probe.get("streams", [])
        duration = float(probe.get("format", {}).get("duration", 0.0))
        text_ok = [line["original_text"] for line in lines] == [line.original_text for line in source_lines]
        ranges_ok = all(0 <= line["start"] <= line["end"] <= 25.0 for line in lines)
        report = {"song_id": song_id, "source_duration_seconds": timing["audio"]["duration_seconds"],
                  "lyric_events": len(lines), "estimated_timing_events": len(result["estimated_line_ids"]),
                  "preview_start_seconds": start, "preview_end_seconds": start + 25,
                  "preview_duration_seconds": duration, "render_runtime_seconds": result["render_runtime_seconds"],
                  "output_path": result["video"], "subtitle_paths": result["subtitle_paths"],
                  "qc_frame_path": f"work/focus/render_qc/preview_{song_id}.png",
                  "qc": {"authoritative_text_exact": text_ok, "ranges_valid": ranges_ok,
                         "resolution_1080p": any(s.get("width") == 1920 and s.get("height") == 1080 for s in streams),
                         "has_audio": any(s.get("codec_type") == "audio" for s in streams),
                         "duration_25_seconds": abs(duration - 25.0) < 0.25,
                         "ffmpeg_success": True}}
        report["qc"]["valid"] = all(report["qc"].values())
        (report_dir / f"{song_id}.json").write_text(json.dumps(report, indent=2) + "\n")
        summaries.append(report)
        print(json.dumps({"song_id": song_id, "runtime": report["render_runtime_seconds"], "qc": report["qc"]["valid"]}))
    (report_dir / "summary.json").write_text(json.dumps({"songs": summaries, "all_valid": all(item["qc"]["valid"] for item in summaries)}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
