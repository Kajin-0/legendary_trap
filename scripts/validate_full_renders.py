#!/usr/bin/env python3
"""Validate completed lyric visualizer renders without acoustic-quality gates."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from legendary_trap.validation import validate

ROOT = Path(__file__).resolve().parents[1]
FFPROBE = ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffprobe"
SONGS = ["apple", "chokehold", "commin_long_ways", "off_the_wave", "slidin",
         "we_got_chemistry", "you_missed_it"]


def probe(path: Path) -> dict:
    result = subprocess.run(
        [str(FFPROBE), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=30,
    )
    return json.loads(result.stdout)


def main() -> int:
    manifest = json.loads((ROOT / "song_manifest.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in manifest["songs"]}
    report_dir = ROOT / "reports" / "visualizer_full"
    report_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for song_id in SONGS:
        item = by_id[song_id]
        out_dir = ROOT / "output" / song_id
        video = out_dir / f"{song_id}.mp4"
        timing_path = out_dir / "render_timing.json" if (out_dir / "render_timing.json").exists() else out_dir / "timing.json"
        diagnostics_path = out_dir / f"{song_id}.render_diagnostics.json"
        document = json.loads(timing_path.read_text(encoding="utf-8"))
        media = probe(video)
        streams = media.get("streams", [])
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
        audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
        validation = validate(document, ROOT / item["lyrics_path"], item["lyrics_sha256"],
                              float(document["audio"]["duration_seconds"]))
        duration = float(media.get("format", {}).get("duration", 0.0))
        expected = float(document["audio"]["duration_seconds"])
        report = {
            "song_id": song_id,
            "video": str(video.relative_to(ROOT)),
            "timing": str(timing_path.relative_to(ROOT)),
            "subtitle_paths": {ext: str((out_dir / f"{song_id}.{ext}").relative_to(ROOT)) for ext in ("ass", "srt", "vtt")},
            "duration_seconds": expected,
            "video_duration_seconds": round(duration, 3),
            "estimated_line_count": len([line for section in document["sections"] for line in section["lines"]
                                          if line.get("estimated_timing")]),
            "line_count": sum(len(section["lines"]) for section in document["sections"]),
            "render_runtime_seconds": json.loads(diagnostics_path.read_text(encoding="utf-8")).get("render_runtime_seconds")
            if diagnostics_path.exists() else None,
            "media": {
                "resolution": f"{video_stream.get('width')}x{video_stream.get('height')}",
                "fps": video_stream.get("r_frame_rate"),
                "video_codec": video_stream.get("codec_name"),
                "audio_codec": audio_stream.get("codec_name"),
                "has_audio": bool(audio_stream),
            },
            "validation": validation,
        }
        report["qc"] = {
            "video_exists": video.exists(),
            "resolution_1080p": video_stream.get("width") == 1920 and video_stream.get("height") == 1080,
            "has_audio": bool(audio_stream),
            "duration_matches_timing": abs(duration - expected) <= 0.5,
            "ffprobe_success": True,
            "valid": bool(video.exists() and validation["valid"] and report["media"]["resolution"] == "1920x1080"
                              and bool(audio_stream) and abs(duration - expected) <= 0.5),
        }
        (report_dir / f"{song_id}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        reports.append(report)
    summary = {"songs": reports, "all_valid": all(report["qc"]["valid"] for report in reports)}
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"all_valid": summary["all_valid"], "songs": len(reports)}))
    return 0 if summary["all_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
