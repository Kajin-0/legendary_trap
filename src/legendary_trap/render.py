"""Render one song into a restrained, audio-reactive lyric visualizer."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from copy import deepcopy
from pathlib import Path

from .lyric_timing import (
    DEFAULT_ESTIMATED_LINES,
    build_estimated_document,
    complete_estimated_lines,
    estimated_line_ids,
)
from .lyrics import parse_lyrics
from .subtitle_render import write_subtitles

ROOT = Path(__file__).resolve().parents[2]
FFMPEG = ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffmpeg"


def build_filter(ass_path: Path, title: str) -> str:
    """Build the fixed 1080p visual language; audio drives the waveform layer."""
    subtitle_path = str(ass_path).replace("\\", "\\\\").replace(":", r"\:")
    return (
        "[0:a]aformat=sample_rates=44100:channel_layouts=stereo,"
        "showwaves=s=1700x190:mode=line:colors=0x61d9ff@0.90:rate=30,format=rgba[wave];"
        "color=c=0x070b14:s=1920x1080:r=30,format=rgba,"
        "noise=alls=4:allf=t+u,"
        "drawbox=x=70:y=58:w=1780:h=964:color=0x1b3850@0.55:t=2[base];"
        "[base][wave]overlay=x=110:y=760:shortest=1,"
        f"subtitles='{subtitle_path}'[v]"
    )


def render(song_id: str, timeout_seconds: int = 900, preview_start: float | None = None,
           preview_duration: float | None = None) -> dict:
    manifest = json.loads((ROOT / "song_manifest.json").read_text(encoding="utf-8"))
    song = next(item for item in manifest["songs"] if item["id"] == song_id)
    source = ROOT / "source" / song["audio_source"]
    reference = ROOT / "output" / song_id / "timing.json"
    output_dir = ROOT / "output" / song_id if preview_start is None else ROOT / "output" / "previews"
    if reference.exists():
        document = json.loads(reference.read_text(encoding="utf-8"))
    else:
        parsed = parse_lyrics(ROOT / song["lyrics_path"], song_id)
        duration_probe = subprocess.run([str(ROOT / "tools/ffmpeg-7.0.2-amd64-static/ffprobe"), "-v", "error",
                                         "-show_entries", "format=duration", "-of", "csv=p=0", str(source)],
                                        check=True, capture_output=True, text=True, timeout=30)
        document = build_estimated_document(parsed, float(duration_probe.stdout.strip()), song_id,
                                            str(source.relative_to(ROOT)))
    # The high-capacity FOCUS experiment is the best existing evidence. Merge
    # only its accepted rows; authoritative text and all other rows remain in
    # the canonical reference document.
    recovered_path = ROOT / "reports" / "focus_large_whisper" / "recovered_lines.json"
    if song_id == "focus" and recovered_path.exists():
        recovered = json.loads(recovered_path.read_text(encoding="utf-8"))
        by_id = {row["line_id"]: row for row in recovered.get("lines", [])
                 if row.get("accepted_direct_evidence")}
        for section in document["sections"]:
            for line in section["lines"]:
                row = by_id.get(line["line_id"])
                if not row:
                    continue
                line["start"], line["end"] = row["start"], row["end"]
                line["confidence"] = row.get("probability_mean", line["confidence"])
                line["matched_tokens"] = row.get("accepted_tokens", line.get("matched_tokens", 0))
                line["acoustic_start"], line["acoustic_end"] = row["start"], row["end"]
                line["timing_source"] = "asr_distil_large_v3"
                line["estimated_timing"] = False
                if row.get("words"):
                    line["words"] = [{**word, "confidence": word.get("probability", 0.0)}
                                     for word in row["words"]]
    duration = float(document["audio"]["duration_seconds"])
    all_invalid = {line["line_id"] for section in document["sections"] for line in section["lines"]
                   if float(line.get("end", 0.0)) <= float(line.get("start", 0.0))}
    document = complete_estimated_lines(document, duration, DEFAULT_ESTIMATED_LINES | all_invalid)
    render_document = document
    if preview_start is not None:
        start = max(0.0, preview_start)
        end = min(float(document["audio"]["duration_seconds"]), start + (preview_duration or 25.0))
        render_document = deepcopy(document)
        clip_duration = end - start
        for section in render_document["sections"]:
            for line in section["lines"]:
                line["start"] = round(min(clip_duration, max(0.0, line["start"] - start)), 3)
                line["end"] = round(min(clip_duration, max(0.0, line["end"] - start)), 3)
                for word in line.get("words", []):
                    word["start"] = round(min(clip_duration, max(0.0, word["start"] - start)), 3)
                    word["end"] = round(min(clip_duration, max(0.0, word["end"] - start)), 3)
        render_document["audio"]["duration_seconds"] = round(end - start, 3)
    subtitle_paths = write_subtitles(render_document, output_dir, song_id)
    if preview_start is None and not reference.exists():
        timing_path = output_dir / "timing.json"
    elif preview_start is not None:
        timing_path = output_dir / f"{song_id}.timing.json"
    else:
        timing_path = output_dir / "render_timing.json"
    timing_path.write_text(json.dumps(render_document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    video = output_dir / f"{song_id}.mp4"
    seek = ["-ss", str(start)] if preview_start is not None else []
    length = ["-t", str(end - start)] if preview_start is not None else []
    command = [str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error", *seek, *length, "-i", str(source),
               "-filter_complex", build_filter(Path(subtitle_paths["ass"]), song_id),
               "-map", "[v]", "-map", "0:a:0", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", "-shortest", str(video)]
    started = time.perf_counter()
    subprocess.run(command, check=True, timeout=timeout_seconds)
    runtime = round(time.perf_counter() - started, 3)
    return {"song_id": song_id, "video": str(video.relative_to(ROOT)), "resolution": "1920x1080",
            "fps": 30, "duration_seconds": duration, "render_runtime_seconds": runtime,
            "subtitle_line_count": sum(len(s["lines"]) for s in render_document["sections"]),
            "estimated_line_ids": estimated_line_ids(render_document), "subtitle_paths": subtitle_paths,
            "timing_path": str(timing_path.relative_to(ROOT)), "command": command}


def main() -> int:
    parser = argparse.ArgumentParser(description="Render one lyric visualizer")
    parser.add_argument("song_id", choices=["apple", "chokehold", "commin_long_ways", "focus",
                                             "off_the_wave", "slidin", "we_got_chemistry", "you_missed_it"])
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--preview-start", type=float)
    parser.add_argument("--preview-duration", type=float, default=25.0)
    args = parser.parse_args()
    result = render(args.song_id, args.timeout, args.preview_start, args.preview_duration)
    print(json.dumps(result, indent=2))
    diagnostics_dir = ROOT / "output" / args.song_id if args.preview_start is None else ROOT / "output" / "previews"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    (diagnostics_dir / f"{args.song_id}.render_diagnostics.json").write_text(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
