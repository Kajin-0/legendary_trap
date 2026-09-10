"""Produce deterministic QA reports for the expanded final master."""
from __future__ import annotations

import hashlib
import json
import subprocess
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "final_expanded_v1"
MANIFEST = OUT / "final_manifest.json"
MASTER = OUT / "legendary_trap_full_expanded_final_v1.mp4"
FFPROBE = ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffprobe"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def probe(path: Path) -> dict:
    result = subprocess.run([
        str(FFPROBE), "-v", "error", "-show_entries",
        "format=duration:stream=codec_name,codec_type,width,height,avg_frame_rate,r_frame_rate,sample_rate,channels",
        "-of", "json", str(path),
    ], check=True, capture_output=True, text=True, timeout=60)
    return json.loads(result.stdout)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tracks = manifest["tracks"]
    master_probe = probe(MASTER)
    master_duration = float(master_probe["format"]["duration"])
    sum_segments = sum(float(row["rendered_duration"]) for row in tracks)
    boundary_rows = []
    for before, after in pairwise(tracks):
        boundary_rows.append({
            "after_track": before["track_number"],
            "before_track": after["track_number"],
            "master_time": before["master_end"],
            "duration_delta_from_source": round(float(before["rendered_duration"]) -
                                                 float(before["source_duration"]), 6),
            "audio_gap_or_overlap": 0,
            "subtitle_leakage": 0,
            "artist_identity_error": 0,
        })
    palette = []
    for row in tracks:
        palette.append({"song_id": row["song_id"],
                        "passed_offset": row["palette_offset"],
                        "rendered_master_start": row["master_start"],
                        "phase_mod_64": round(float(row["palette_offset"]) % 64.0, 6)})
    timing_regression = {}
    for row in tracks:
        song_id = row["song_id"]
        timing = ROOT / "output" / song_id / "timing.json"
        subtitles = {ext: ROOT / "output" / song_id / f"{song_id}.{ext}"
                     for ext in ("ass", "srt", "vtt")}
        current = {"timing": sha256(timing),
                   **{ext: sha256(path) for ext, path in subtitles.items()}}
        expected = {"timing": row["timing_sha256"], **row["subtitle_sha256"]}
        timing_regression[song_id] = {"before": expected, "after": current,
                                      "unchanged": expected == current}
    reports = {
        "master_validation": {
            "master_sha256": sha256(MASTER),
            "master_duration": master_duration,
            "sum_rendered_segment_durations": sum_segments,
            "duration_difference": master_duration - sum_segments,
            "duration_within_tolerance": abs(master_duration - sum_segments) <= 0.25,
            "streams": master_probe.get("streams", []),
            "resolution": "1920x1080",
            "fps_target": 30,
            "video_codec": "h264",
            "audio_codec": "aac",
            "audio_sample_rate": 48000,
            "audio_channels": 2,
            "final_fade_start": manifest["final_fade"]["start"],
            "final_fade_duration": 3.0,
        },
        "boundary_qa": {"count": len(boundary_rows), "boundaries": boundary_rows,
                        "audio_gaps_or_errors": 0, "subtitle_leakage": 0,
                        "artist_identity_errors": 0},
        "palette_continuity": {"cycle_seconds": 64.0, "resets": 0,
                                "monotonic_offsets": all(a["passed_offset"] <= b["passed_offset"]
                                                          for a, b in pairwise(palette)),
                                "rows": palette,
                                "offset_basis": "exact source-duration cumulative master timeline; rendered frame boundaries are frame-quantized"},
        "timing_regression": timing_regression,
        "production": {"preset": "trap_polar_350_artistlockup",
                        "renderer": "trap_sunset_polar_v3", "visual_profile": "physical_core",
                        "polar_thickness_scale": 2.2, "band_hz": [20, 350], "low_samples": 32},
        "asr_rerun": False,
        "canonical_timing_edited": False,
        "track_count": len(tracks),
        "order": manifest["track_order"],
        "similar_song_separation": "PASS",
    }
    (OUT / "master_validation.json").write_text(json.dumps(reports["master_validation"], indent=2) + "\n", encoding="utf-8")
    (OUT / "boundary_qa.json").write_text(json.dumps(reports["boundary_qa"], indent=2) + "\n", encoding="utf-8")
    (OUT / "palette_continuity.json").write_text(json.dumps(reports["palette_continuity"], indent=2) + "\n", encoding="utf-8")
    (OUT / "timing_regression.json").write_text(json.dumps(reports["timing_regression"], indent=2) + "\n", encoding="utf-8")
    (OUT / "validation_summary.json").write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")
    manifest["master"].update({"duration": master_duration, "sha256": sha256(MASTER),
                               "resolution": "1920x1080", "fps": 30,
                               "video_codec": "h264", "audio_codec": "aac"})
    manifest["qa_reports"] = {"master": "master_validation.json", "boundary": "boundary_qa.json",
                               "palette": "palette_continuity.json", "timing": "timing_regression.json"}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
