"""Deterministic procedural visualizer presets for short aesthetic previews."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.ndimage import rotate

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
    "trap_sunset_hybrid": Preset("trap_sunset_hybrid", (8, 5, 16), (242, 128, 73),
                                  (104, 81, 202), "trap_sunset_hybrid", 126, 360),
    "trap_sunset_hybrid_v2": Preset("trap_sunset_hybrid_v2", (8, 5, 16), (242, 128, 73),
                                     (104, 81, 202), "trap_sunset_hybrid", 126, 360),
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


def _hybrid_particles(preset: Preset) -> tuple[np.ndarray, ...]:
    """Create three deterministic depth classes with inertial base velocities."""
    rng = np.random.default_rng(78123)
    count = preset.particle_count
    positions = rng.random((count, 2), dtype=np.float32)
    depths = np.repeat(np.array([0.25, 0.55, 0.90], dtype=np.float32), count // 3)
    depths = np.pad(depths, (0, count - len(depths)), constant_values=0.55)
    velocity = rng.normal(0, 1, (count, 2)).astype(np.float32)
    velocity[:, 0] += 0.35 + depths * 0.7
    velocity[:, 1] *= 0.28
    phases = rng.uniform(0, 6.28, count).astype(np.float32)
    return positions, depths, velocity, phases


def _hybrid_frame(features: FeatureSequence, index: int, preset: Preset,
                  particles: tuple[np.ndarray, ...]) -> np.ndarray:
    """Render a dusk landscape whose physical pressure is driven by the low end."""
    t = index / features.fps
    bass, mids, highs = (float(features.bass[index]), float(features.mids[index]),
                         float(features.highs[index]))
    transient = float(features.transients[index])
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float32)
    # Explicit day-to-sunset trajectory: smooth, slow, and independent of audio.
    stops = np.array([[68, 126, 173], [235, 173, 96], [224, 103, 70],
                      [192, 86, 140], [70, 68, 145]], dtype=np.float32)
    progress = np.clip(t / 18.0, 0.0, 1.0)
    smooth_progress = progress * progress * (3.0 - 2.0 * progress)
    position = smooth_progress * (len(stops) - 1)
    left = min(len(stops) - 2, int(position))
    palette = stops[left] * (1 - position % 1) + stops[left + 1] * (position % 1)
    top = palette * 0.82 + np.array([0, 4, 8], dtype=np.float32)
    bottom = palette * 0.96 + np.array([12, 0, 8], dtype=np.float32)
    vertical = (yy / HEIGHT)[..., None]
    frame[:] = top * (1 - vertical) + bottom * vertical
    # Moving sunset disc and haze layers establish depth without becoming literal footage.
    sun_x = WIDTH * (0.68 + 0.025 * np.sin(t * 0.09))
    sun_y = HEIGHT * 0.47
    sun_distance = ((xx - sun_x) ** 2 + ((yy - sun_y) * 1.15) ** 2) / (190 + bass * 50) ** 2
    sun = np.exp(-sun_distance * 2.1) * (0.18 + 0.12 * bass + 0.05 * transient)
    sun_color = np.array([255, 218, 142], dtype=np.float32) * (1 - smooth_progress) + np.array([255, 106, 97], dtype=np.float32) * smooth_progress
    frame = frame * (1 - sun[..., None]) + sun_color * sun[..., None]
    haze = np.exp(-((yy / HEIGHT - 0.54) ** 2) / 0.055) * (0.06 + 0.08 * mids)
    haze_color = palette * 0.62 + np.array([35, 16, 24], dtype=np.float32)
    frame = frame * (1 - haze[..., None]) + haze_color * haze[..., None]
    # Distant layered terrain and a low road/horizon silhouette.
    horizon = HEIGHT * 0.66
    distant = horizon - 32 - 20 * np.sin(xx / 100 + t * 0.04) - 11 * np.sin(xx / 37 - t * 0.02)
    near = horizon - 11 - 35 * np.sin(xx / 145 + 1.2 + t * 0.025) - 13 * np.sin(xx / 53)
    frame[yy > distant] *= 0.78
    frame[yy > near] *= 0.50
    ground = yy > horizon + 4
    frame[ground] *= 0.56
    # Bass pressure swells the horizon luminance and compresses the frame edges.
    frame *= (1 + 0.10 * bass + 0.07 * transient)
    # Inertial particles: velocity classes receive a decaying kick impulse.
    positions, depths, velocity, phases = particles
    history_start = max(0, index - 14)
    impulse = float(np.sum(features.transients[history_start:index + 1] *
                            np.exp(-np.linspace(0, 2.8, index - history_start + 1))))
    speed = 0.18 + 0.16 * bass + 0.22 * impulse
    px = (positions[:, 0] + velocity[:, 0] * t * speed * (0.3 + depths) +
          np.sin(phases + t * 0.25) * 0.006 * (1 + bass * 2)) % 1.0
    py = (positions[:, 1] + velocity[:, 1] * t * speed +
          np.cos(phases * 0.8 + t * 0.18) * 0.004) % 1.0
    px, py = (px * WIDTH).astype(np.int32), (py * HEIGHT).astype(np.int32)
    particle_alpha = (0.035 + depths * (0.09 + 0.14 * highs + 0.10 * transient)).astype(np.float32)
    particle_color = tuple(np.clip(palette * 0.72 + np.array([65, 50, 42]), 0, 255))
    _blend(frame, px, py, particle_color, particle_alpha)
    # Low-centered filled energy ribbon: integrated mass replaces the analyzer strip.
    x = np.linspace(90, WIDTH - 90, 640)
    raw_spectrum = np.interp(x, np.linspace(90, WIDTH - 90, len(features.spectrum[index])), features.spectrum[index])
    smooth_spectrum = np.convolve(raw_spectrum, np.ones(17) / 17, mode="same")
    low_bias = 1.22 - 0.42 * np.linspace(0, 1, len(raw_spectrum))
    envelope = np.clip(smooth_spectrum * low_bias + mids * 0.12, 0, 1)
    baseline = HEIGHT * 0.60
    body = 16 + envelope * (34 + 62 * bass) + mids * 9
    glow_color = tuple(np.clip(palette * 0.84 + np.array([20, 15, 8]), 0, 255))
    fill_levels = np.linspace(0.02, 1.0, 54)
    fill_x = np.tile(x, len(fill_levels))
    fill_y = np.concatenate([baseline - body * fill for fill in fill_levels])
    fill_alpha = np.repeat(np.linspace(0.022, 0.095, len(fill_levels)), len(x))
    _blend(frame, fill_x, fill_y, glow_color, fill_alpha)
    # A second, dense half-pixel body keeps the shape smooth instead of dotted.
    dense_x = np.repeat(x, 3)
    dense_y = np.repeat(baseline - body, 3) + np.tile([0.0, 1.0, 2.0], len(x))
    _blend(frame, dense_x, dense_y, glow_color, 0.16)
    detail = np.clip(envelope + (raw_spectrum - smooth_spectrum) * (0.25 + highs * 0.35), 0, 1)
    core_color = tuple(np.clip(palette * 0.58 + np.array([105, 82, 65]), 0, 255))
    _blend(frame, x, baseline - (16 + detail * (34 + 62 * bass) + mids * 9), core_color, 0.94)
    # Broad reflected haze, deliberately too soft to read as a second equalizer band.
    _blend(frame, x, baseline + 48 + envelope * 18, tuple(np.clip(palette * 0.55, 0, 255)), 0.055 + bass * 0.035)
    # Reactive edge vignette: pressure tightens, then relaxes with attack/release.
    edge = np.clip(((xx - WIDTH / 2) / (WIDTH / 2)) ** 2 +
                   ((yy - HEIGHT / 2) / (HEIGHT / 2)) ** 2, 0, 1)
    vignette = 1 - edge ** (1.25 - 0.18 * bass - 0.12 * transient) * (0.30 + 0.25 * bass + 0.12 * transient)
    frame *= vignette[..., None]
    vignette_tint = np.clip(palette * 0.18 * edge[..., None] * (0.35 + 0.65 * bass), 0, 30)
    frame = np.clip(frame + vignette_tint, 0, 255)
    # A restrained impact tint follows the transient rather than blinking the frame.
    frame += np.clip(transient * 18, 0, 18)
    # Few-pixel kick-linked camera displacement and signed sub-degree rotation.
    shake = min(4.0, 0.8 * transient + 0.35 * bass)
    offset_x = int(np.sin(t * 48.0 + 0.4) * shake)
    offset_y = int(np.cos(t * 41.0 + 0.7) * shake * 0.55)
    rotation = np.sin(t * 39.0 + 1.1) * transient * 0.16 + np.sin(t * 2.7) * bass * 0.035
    frame = rotate(frame, float(rotation), reshape=False, order=1, mode="nearest", prefilter=False)
    frame = np.roll(frame, (offset_y, offset_x), axis=(0, 1))
    return np.clip(frame, 0, 255).astype(np.uint8)


def render_frame(features: FeatureSequence, index: int, preset: Preset,
                 particles: tuple[np.ndarray, ...]) -> np.ndarray:
    if preset.visualizer == "trap_sunset_hybrid":
        return _hybrid_frame(features, index, preset, particles)
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
    display_title = song_id.replace("_", " ").upper()
    subtitle_paths = write_subtitles(render_document, output_dir, display_title)
    features = extract_features(source, start, duration, FPS)
    preset = PRESETS[preset_name]
    particles = _hybrid_particles(preset) if preset.visualizer == "trap_sunset_hybrid" else _particles(preset)
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
