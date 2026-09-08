"""Apply the final three-second video/audio fade using measured duration."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffmpeg"
FFPROBE = ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffprobe"


def duration(path: Path) -> float:
    result = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                             "-of", "json", str(path)], check=True, capture_output=True,
                            text=True, timeout=30)
    return float(json.loads(result.stdout)["format"]["duration"])


def main() -> None:
    raw, output = map(Path, sys.argv[1:3])
    measured = duration(raw)
    start = measured - 3.0
    if start <= 0:
        raise ValueError("final segment is shorter than the requested fade")
    command = [str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
               "-vf", f"fade=t=out:st={start:.6f}:d=3", "-af", f"afade=t=out:st={start:.6f}:d=3",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
               "-r", "30", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output)]
    subprocess.run(command, check=True, timeout=900)
    print(json.dumps({"input_duration": measured, "fade_start": start,
                      "duration": duration(output), "output": str(output)}))


if __name__ == "__main__":
    main()
