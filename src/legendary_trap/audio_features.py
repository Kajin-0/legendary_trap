"""Small deterministic audio-feature extraction for visualizer motion."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


@dataclass(frozen=True)
class FeatureSequence:
    fps: int
    spectrum: np.ndarray
    bass: np.ndarray
    mids: np.ndarray
    highs: np.ndarray
    rms: np.ndarray
    transients: np.ndarray


def _normalize(values: np.ndarray) -> np.ndarray:
    low, high = np.percentile(values, [10, 95])
    return np.clip((values - low) / max(1e-6, high - low), 0.0, 1.0).astype(np.float32)


def _smooth(values: np.ndarray, attack: float, release: float) -> np.ndarray:
    result = np.empty_like(values, dtype=np.float32)
    previous = 0.0
    for index, value in enumerate(values):
        coefficient = attack if value > previous else release
        previous += coefficient * (float(value) - previous)
        result[index] = previous
    return result


def extract_features(path: Path, start: float, duration: float, fps: int = 30,
                     bins: int = 256) -> FeatureSequence:
    audio, sample_rate = sf.read(path, start=max(0, int(start * 48000)),
                                 frames=max(1, int((duration + 0.2) * 48000)),
                                 dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    if sample_rate != 48000:
        # Project source files are 48 kHz; fail clearly instead of silently
        # applying the wrong frame-to-time mapping to an unusual asset.
        raise ValueError(f"expected 48 kHz source audio, got {sample_rate}")
    frame_count = max(1, round(duration * fps))
    fft_size = 4096
    window = np.hanning(fft_size).astype(np.float32)
    frequencies = np.fft.rfftfreq(fft_size, 1 / sample_rate)
    spectrum = np.zeros((frame_count, bins), dtype=np.float32)
    bass = np.zeros(frame_count, dtype=np.float32)
    mids = np.zeros(frame_count, dtype=np.float32)
    highs = np.zeros(frame_count, dtype=np.float32)
    rms = np.zeros(frame_count, dtype=np.float32)
    for index in range(frame_count):
        center = int((index + 0.5) * sample_rate / fps)
        left = max(0, min(len(mono), center - fft_size // 2))
        chunk = np.zeros(fft_size, dtype=np.float32)
        available = mono[left:min(len(mono), left + fft_size)]
        chunk[:len(available)] = available
        rms[index] = np.sqrt(np.mean(chunk * chunk) + 1e-8)
        magnitudes = np.abs(np.fft.rfft(chunk * window)).astype(np.float32)
        log_magnitudes = np.log1p(magnitudes)
        reshaped = np.interp(np.linspace(0, len(log_magnitudes) - 1, bins),
                             np.arange(len(log_magnitudes)), log_magnitudes)
        spectrum[index] = reshaped
        bass[index] = log_magnitudes[(frequencies >= 20) & (frequencies < 180)].mean()
        mids[index] = log_magnitudes[(frequencies >= 180) & (frequencies < 2500)].mean()
        highs[index] = log_magnitudes[frequencies >= 2500].mean()
    normalized_spectrum = np.clip(spectrum / np.percentile(spectrum, 98), 0, 1)
    bass = _smooth(_normalize(bass), 0.24, 0.06)
    mids = _smooth(_normalize(mids), 0.38, 0.12)
    highs = _smooth(_normalize(highs), 0.62, 0.24)
    rms = _smooth(_normalize(rms), 0.28, 0.10)
    delta = np.maximum(0.0, np.diff(np.r_[rms[0], rms]))
    transients = _smooth(_normalize(delta), 0.75, 0.18)
    return FeatureSequence(fps, normalized_spectrum.astype(np.float32), bass, mids, highs, rms, transients)
