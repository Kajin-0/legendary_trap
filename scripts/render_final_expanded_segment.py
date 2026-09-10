"""Render and validate one resumable physical_core final-master segment."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from legendary_trap.visualizer import (
    APPROVED_POLAR_LOW_MAX_HZ,
    PRODUCTION_POLAR_THICKNESS_SCALE,
    PRODUCTION_REVIEW_PRESET,
    PRODUCTION_VISUAL_PROFILE,
    STANDALONE_SONGS,
    render_preview,
)

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffmpeg"
FFPROBE = ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffprobe"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def probe(path: Path) -> dict:
    result = subprocess.run([
        str(FFPROBE), "-v", "error", "-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height,avg_frame_rate,sample_rate,channels,nb_frames,duration",
        "-of", "json", str(path),
    ], check=True, capture_output=True, text=True, timeout=60)
    data = json.loads(result.stdout)
    return {"format": data.get("format", {}), "streams": data.get("streams", [])}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("song_id")
    parser.add_argument("track_number", type=int)
    parser.add_argument("output", type=Path)
    parser.add_argument("--palette-offset", type=float, required=True)
    parser.add_argument("--source-duration", type=float, required=True)
    parser.add_argument("--fade-final", action="store_true")
    args = parser.parse_args()

    timing_path = ROOT / "output" / args.song_id / "timing.json"
    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    source_name = timing.get("audio", {}).get("source")
    if args.song_id in STANDALONE_SONGS:
        source_name = STANDALONE_SONGS[args.song_id]["audio_source"]
    else:
        manifest = json.loads((ROOT / "song_manifest.json").read_text(encoding="utf-8"))
        source_name = next(item["audio_source"] for item in manifest["songs"]
                            if item["id"] == args.song_id)
    source = ROOT / "source" / source_name
    subtitle_paths = [ROOT / "output" / args.song_id / f"{args.song_id}.{ext}"
                      for ext in ("ass", "srt", "vtt")]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = render_preview(
        args.song_id, PRODUCTION_REVIEW_PRESET, 0.0, args.source_duration,
        timeout_seconds=2400, lyric_font="Barlow Condensed", lyric_size=90,
        low_max_hz=APPROVED_POLAR_LOW_MAX_HZ, identity_enabled=True,
        output_path=(ROOT / args.output), palette_time_offset=args.palette_offset,
        polar_thickness_scale=PRODUCTION_POLAR_THICKNESS_SCALE,
        visual_profile=PRODUCTION_VISUAL_PROFILE,
    )
    if args.fade_final:
        faded = (ROOT / args.output).with_suffix(".fade.mp4")
        fade_start = max(0.0, args.source_duration - 3.0)
        subprocess.run([
            str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(ROOT / args.output),
            "-vf", f"fade=t=out:st={fade_start:.6f}:d=3",
            "-af", f"afade=t=out:st={fade_start:.6f}:d=3",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k",
            "-t", str(args.source_duration), "-movflags", "+faststart", str(faded),
        ], check=True, timeout=2400)
        os.replace(faded, ROOT / args.output)
    video_probe = probe(ROOT / args.output)
    video_stream = next(s for s in video_probe["streams"] if s.get("codec_type") == "video")
    audio_stream = next(s for s in video_probe["streams"] if s.get("codec_type") == "audio")
    manifest = json.loads((ROOT / "configs" / "songs.json").read_text(encoding="utf-8"))
    artist_id = manifest["songs"][args.song_id]["artists"][0]
    artists = json.loads((ROOT / "configs" / "artists.json").read_text(encoding="utf-8"))["artists"]
    artist = artists[artist_id]
    sidecar = {
        "song_id": args.song_id,
        "track_number": args.track_number,
        "source_sha256": sha256(source),
        "timing_sha256": sha256(timing_path),
        "subtitle_sha256": {path.suffix[1:]: sha256(path) for path in subtitle_paths},
        "artist": artist["display_name"],
        "artist_id": artist_id,
        "artist_pfp": artist.get("pfp"),
        "artist_crop": artist.get("crop"),
        "preset": PRODUCTION_REVIEW_PRESET,
        "renderer": "trap_sunset_polar_v3",
        "visual_profile": PRODUCTION_VISUAL_PROFILE,
        "polar_thickness_scale": PRODUCTION_POLAR_THICKNESS_SCALE,
        "polar_band": [20, 350],
        "low_samples": 32,
        "palette_time_offset": args.palette_offset,
        "source_duration": args.source_duration,
        "rendered_duration": float(video_probe["format"]["duration"]),
        "audio_duration": float(next(s for s in video_probe["streams"]
                                      if s.get("codec_type") == "audio").get("duration", 0.0) or 0.0),
        "frame_count": int(video_stream.get("nb_frames", 0) or 0),
        "video_sha256": sha256(ROOT / args.output),
        "video_stream": video_stream,
        "audio_stream": audio_stream,
        "render_result": result,
        "final_fade": {"duration": 3.0, "applied": bool(args.fade_final)},
    }
    sidecar_path = (ROOT / args.output).with_suffix(".json")
    sidecar_path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(sidecar, indent=2))


if __name__ == "__main__":
    main()
