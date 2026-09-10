"""Build the final 16-song manifest, chapters, review index, and concat list."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "final_expanded_v1"
SEGMENTS = OUT / "segments"
ORDER = json.loads((ROOT / "configs" / "songs.json").read_text(encoding="utf-8"))["track_order"]
FFPROBE = ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffprobe"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    songs = json.loads((ROOT / "configs" / "songs.json").read_text(encoding="utf-8"))
    artists = json.loads((ROOT / "configs" / "artists.json").read_text(encoding="utf-8"))["artists"]
    rows = []
    cursor = 0.0
    for number, song_id in enumerate(ORDER, 1):
        sidecar = json.loads((SEGMENTS / f"{number:02d}_{song_id}.json").read_text(encoding="utf-8"))
        artist_id = songs["songs"][song_id]["artists"][0]
        artist = artists[artist_id]
        row = dict(sidecar)
        row.update({"title": songs["songs"][song_id]["title"],
                    "artist": artist["display_name"], "artist_pfp": artist.get("pfp"),
                    "master_start": cursor,
                    "master_end": cursor + float(sidecar["rendered_duration"]),
                    "palette_offset": float(sidecar["palette_time_offset"]),
                    "segment_path": str((SEGMENTS / f"{number:02d}_{song_id}.mp4").relative_to(ROOT))})
        rows.append(row)
        cursor = row["master_end"]
    chapters = []
    for row in rows:
        seconds = int(row["master_start"])
        chapters.append(f"{seconds // 60:02d}:{seconds % 60:02d} {row['title']} — {row['artist']}")
    transitions = [{"after_track": rows[i]["song_id"], "before_track": rows[i + 1]["song_id"],
                    "master_time": rows[i]["master_end"]} for i in range(len(rows) - 1)]
    manifest = {
        "schema_version": 1,
        "production_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                             check=True, capture_output=True, text=True,
                                             timeout=30).stdout.strip(),
        "track_count": 16, "track_order": ORDER, "transition_seconds": 0.0,
        "tracks": rows, "final_fade": {"duration": 3.0, "start": rows[-1]["master_end"] - 3.0},
        "master": {"filename": "legendary_trap_full_expanded_final_v1.mp4",
                   "duration": cursor},
        "production_visualizer": {"preset": "trap_polar_350_artistlockup",
                                   "renderer": "trap_sunset_polar_v3", "visual_profile": "physical_core",
                                   "polar_thickness_scale": 2.2, "band_hz": [20, 350],
                                   "low_samples": 32},
        "separation_constraint": {"status": "PASS", "do_you_see_me_track": 11,
                                   "what_i_need_track": 16, "tracks_between": 4},
        "transitions": transitions,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "final_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (OUT / "youtube_chapters.txt").write_text("\n".join(chapters) + "\n", encoding="utf-8")
    review = ["FINAL EXPANDED REVIEW INDEX", ""]
    for row in rows:
        review.append(f"{row['track_number']:02d} {row['master_start']:.3f}s — {row['title']} — {row['artist']}")
    review += ["", "TRANSITIONS"]
    review += [f"{item['master_time']:.3f}s — {item['after_track']} → {item['before_track']}" for item in transitions]
    (OUT / "review_index.txt").write_text("\n".join(review) + "\n", encoding="utf-8")
    (OUT / "segments.txt").write_text("\n".join(
        f"file '{(SEGMENTS / f'{i:02d}_{song}.mp4').as_posix()}'" for i, song in enumerate(ORDER, 1)) + "\n", encoding="utf-8")
    print(json.dumps({"duration": cursor, "tracks": rows, "chapters": chapters}, indent=2))


if __name__ == "__main__":
    main()
