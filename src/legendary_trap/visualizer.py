"""Deterministic procedural visualizer presets for short aesthetic previews."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .audio_features import FeatureSequence, extract_features
from .subtitle_render import write_subtitles

ROOT = Path(__file__).resolve().parents[2]
FFMPEG = ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffmpeg"
WIDTH, HEIGHT = 960, 540
FPS = 30


@dataclass(frozen=True)
class Preset:
    name: str
    background: tuple[float, float, float]
    accent: tuple[float, float, float]
    secondary: tuple[float, float, float]
    visualizer: str
    particle_count: int
    subtitle_y: int


PRESETS = {
    "orbital": Preset("orbital", (5, 8, 18), (75, 216, 255), (154, 92, 255), "orbital", 72, 390),
    "horizon": Preset("horizon", (6, 9, 20), (65, 215, 255), (130, 102, 255), "horizon", 54, 390),
    "atmospheric": Preset("atmospheric", (9, 7, 18), (229, 131, 190), (83, 155, 255), "atmospheric", 96, 360),
}


def _blend(frame: np.ndarray, x: np.ndarray, y: np.ndarray, color: tuple[float, ...], alpha: np.ndarray | float) -> None:
    valid = (x >= 0) & (x < WIDTH) & (y >= 0) & (y < HEIGHT)
    xi, yi = x[valid].astype(np.int32), y[valid].astype(np.int32)
    a = np.asarray(alpha, dtype=np.float32)
    a = np.broadcast_to(a, x.shape)[valid, None]
    rgb = np.asarray(color, dtype=np.float32)[None, :]
    frame[yi, xi] = frame[yi, xi] * (1 - a) + rgb * a


def _particles(preset: Preset) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(90210 + len(preset.name))
    positions = rng.random((preset.particle_count, 2), dtype=np.float32)
    depths = rng.uniform(0.25, 1.0, preset.particle_count).astype(np.float32)
    phases = rng.uniform(0, 6.28, preset.particle_count).astype(np.float32)
    return positions, depths, phases


def render_frame(features: FeatureSequence, index: int, preset: Preset,
                 particles: tuple[np.ndarray, np.ndarray, np.ndarray]) -> np.ndarray:
    t = index / features.fps
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float32)
    # Slow cinematic gradient and two drifting color washes.
    frame[:] = np.asarray(preset.background, dtype=np.float32)
    drift = 0.5 + 0.5 * np.sin(t * 0.22)
    for center_x, center_y, color, strength in [
        (0.28 + 0.08 * np.sin(t * 0.17), 0.35, preset.secondary, 0.25),
        (0.72 + 0.06 * np.cos(t * 0.13), 0.60, preset.accent, 0.16),
    ]:
        distance = ((xx / WIDTH - center_x) ** 2 + (yy / HEIGHT - center_y) ** 2) / 0.22
        glow = np.exp(-distance * 4.0) * strength * (0.8 + 0.2 * drift)
        frame = frame * (1 - glow[..., None]) + np.asarray(color) * glow[..., None]
    frame *= (0.90 + 0.10 * (1 - yy / HEIGHT))[..., None]
    bass, mids, highs = features.bass[index], features.mids[index], features.highs[index]
    spectrum = features.spectrum[index]

    positions, depths, phases = particles
    px = (positions[:, 0] * WIDTH + np.sin(phases + t * (0.08 + depths * 0.15)) * (4 + 12 * depths)).astype(int)
    py = (positions[:, 1] * HEIGHT + np.cos(phases * 0.7 + t * 0.09) * (3 + 8 * depths)).astype(int)
    brightness = (0.04 + 0.18 * depths * (0.35 + highs) * (0.7 + 0.3 * np.sin(phases + t))).astype(np.float32)
    _blend(frame, px, py, preset.accent, brightness)

    if preset.visualizer == "orbital":
        center = np.array([WIDTH * 0.50, HEIGHT * 0.47])
        angles = np.linspace(0, 2 * np.pi, 192, endpoint=False)
        values = np.interp(np.linspace(0, len(spectrum) - 1, len(angles)), np.arange(len(spectrum)), spectrum)
        base_radius = 105 + 20 * bass
        radii = base_radius + values * (52 + 30 * mids)
        for scale, alpha in [(1.28, 0.045), (1.12, 0.09), (1.0, 0.95)]:
            x = center[0] + np.cos(angles) * radii * scale
            y = center[1] + np.sin(angles) * radii * scale * 0.72
            _blend(frame, x, y, preset.secondary if scale > 1 else preset.accent, alpha)
        inner = 86 + bass * 12
        x = center[0] + np.cos(angles) * inner
        y = center[1] + np.sin(angles) * inner * 0.72
        _blend(frame, x, y, preset.accent, 0.24)
        # Dark core preserves a clear lyric-safe center.
        core = ((xx - center[0]) ** 2 + ((yy - center[1]) / 0.72) ** 2) < (inner - 14) ** 2
        frame[core] *= 0.58
    elif preset.visualizer == "horizon":
        x = np.linspace(80, WIDTH - 80, len(spectrum))
        baseline = HEIGHT * 0.57
        height = 12 + spectrum * (54 + bass * 48) + mids * 8
        for scale, alpha in [(2.6, 0.035), (1.6, 0.08), (1.0, 0.9)]:
            _blend(frame, x, baseline - height * scale, preset.accent, alpha)
            _blend(frame, x, baseline + height * scale, preset.secondary, alpha * 0.55)
        reflection = np.exp(-np.linspace(0, 1, len(spectrum)) * 2.3) * (0.08 + 0.12 * bass)
        _blend(frame, x, baseline + 76 + spectrum * 25, preset.secondary, reflection)
    else:
        # Atmospheric preset keeps the visualizer subordinate to the moving light.
        x = np.linspace(150, WIDTH - 150, len(spectrum))
        baseline = HEIGHT * 0.60
        height = 8 + spectrum * (25 + 18 * mids)
        _blend(frame, x, baseline - height, preset.accent, 0.52)
        _blend(frame, x, baseline + height * 0.55, preset.secondary, 0.20)
        pulse = ((xx - WIDTH * (0.48 + 0.02 * np.sin(t * 0.2))) ** 2 +
                 (yy - HEIGHT * 0.43) ** 2) / (210 + bass * 50) ** 2
        frame += np.clip(np.exp(-pulse * 3.0)[..., None] * features.transients[index] * 20, 0, 20)
    return np.clip(frame, 0, 255).astype(np.uint8)


def _write_png(frame: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen([str(FFMPEG), "-y", "-f", "rawvideo", "-pixel_format", "rgb24",
                                "-video_size", f"{WIDTH}x{HEIGHT}", "-framerate", "1", "-i", "-",
                                "-frames:v", "1", str(path)], stdin=subprocess.PIPE)
    try:
        process.communicate(frame.tobytes(), timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise
    if process.returncode:
        raise subprocess.CalledProcessError(process.returncode, process.args)


def render_preview(song_id: str, preset_name: str, start: float, duration: float,
                   timeout_seconds: int = 600) -> dict:
    manifest = json.loads((ROOT / "song_manifest.json").read_text(encoding="utf-8"))
    song = next(item for item in manifest["songs"] if item["id"] == song_id)
    source = ROOT / "source" / song["audio_source"]
    reference = json.loads((ROOT / "output" / song_id / "timing.json").read_text(encoding="utf-8"))
    render_document = json.loads(json.dumps(reference))
    for section in render_document["sections"]:
        for line in section["lines"]:
            line["start"] = round(max(0, min(duration, line["start"] - start)), 3)
            line["end"] = round(max(0, min(duration, line["end"] - start)), 3)
    render_document["audio"]["duration_seconds"] = duration
    output_dir = ROOT / "output" / "aesthetic_previews"
    output_dir.mkdir(parents=True, exist_ok=True)
    subtitle_paths = write_subtitles(render_document, output_dir, preset_name)
    features = extract_features(source, start, duration, FPS)
    preset = PRESETS[preset_name]
    particles = _particles(preset)
    video = output_dir / f"{preset_name}.mp4"
    subtitle_path = str(Path(subtitle_paths["ass"])).replace("\\", "\\\\").replace(":", r"\:")
    command = [str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo",
               "-pixel_format", "rgb24", "-video_size", f"{WIDTH}x{HEIGHT}", "-framerate", str(FPS),
               "-i", "-", "-ss", str(start), "-t", str(duration), "-i", str(source),
               "-filter_complex", f"[0:v]scale=1920:1080:flags=lanczos,subtitles='{subtitle_path}'[v]",
               "-map", "[v]", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k",
               "-shortest", "-movflags", "+faststart", str(video)]
    started = time.perf_counter()
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for index in range(len(features.bass)):
            process.stdin.write(render_frame(features, index, preset, particles).tobytes())
        process.stdin.close()
        process.wait(timeout=timeout_seconds)
    except (BrokenPipeError, subprocess.TimeoutExpired):
        process.kill()
        process.wait()
        raise
    still = output_dir / f"{preset_name}.png"
    _write_png(render_frame(features, len(features.bass) // 2, preset, particles), still)
    return {"preset": preset_name, "song_id": song_id, "start": start, "duration": duration,
            "resolution": "1920x1080", "runtime_seconds": round(time.perf_counter() - started, 3),
            "video": str(video.relative_to(ROOT)), "still": str(still.relative_to(ROOT)),
            "subtitle": str(Path(subtitle_paths["ass"]).relative_to(ROOT))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("preset", choices=sorted(PRESETS))
    parser.add_argument("--song", default="off_the_wave")
    parser.add_argument("--start", type=float, default=20.0)
    parser.add_argument("--duration", type=float, default=18.0)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    print(json.dumps(render_preview(args.song, args.preset, args.start, args.duration, args.timeout), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
