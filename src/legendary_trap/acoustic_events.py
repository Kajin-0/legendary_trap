"""Deterministic bounded acoustic-event localization for line subtitles."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class EventCandidate:
    start: float
    end: float
    score: float
    confidence: float
    evidence: dict[str, float]
    competing_score: float


def _unit(values: np.ndarray) -> np.ndarray:
    low, high = np.percentile(values, [5, 95])
    if high <= low + 1e-9:
        return np.full_like(values, 0.5, dtype=float)
    return np.clip((values - low) / (high - low), 0.0, 1.0)


def _features(audio: np.ndarray, sample_rate: int, start: float, end: float) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    import librosa

    lo, hi = round(start * sample_rate), round(end * sample_rate)
    clip = audio[lo:hi]
    hop = 160
    n_fft = 1024
    stft = np.abs(librosa.stft(clip, n_fft=n_fft, hop_length=hop, center=True))
    rms = librosa.feature.rms(S=stft, frame_length=n_fft, hop_length=hop)[0]
    flux = librosa.onset.onset_strength(S=librosa.amplitude_to_db(stft + 1e-8), sr=sample_rate, hop_length=hop)
    frequencies = librosa.fft_frequencies(sr=sample_rate, n_fft=n_fft)
    vocal = stft[(frequencies >= 120) & (frequencies <= 4000)].sum(axis=0)
    total = stft.sum(axis=0) + 1e-8
    vocal_ratio = vocal / total
    energy_rise = np.maximum(0.0, np.diff(rms, prepend=rms[0]))
    # pYIN is used only as a lightweight local voicing diagnostic. Fail closed
    # if a platform/librosa combination cannot provide it.
    try:
        _, _, voiced_probability = librosa.pyin(
            clip, fmin=70, fmax=500, sr=sample_rate, frame_length=n_fft,
            hop_length=hop, fill_na=0.0,
        )
        voicing = np.nan_to_num(voiced_probability, nan=0.0)
    except (ImportError, RuntimeError, TypeError, ValueError):
        voicing = np.zeros_like(rms)
    length = min(len(rms), len(flux), len(vocal_ratio), len(voicing))
    times = start + np.arange(length) * hop / sample_rate
    return times, {"onset_strength": _unit(flux[:length]), "energy_rise": _unit(energy_rise[:length]),
                   "vocal_band": _unit(vocal_ratio[:length]), "voicing": _unit(voicing[:length]),
                   "rms": rms[:length]}


def locate_event(audio: np.ndarray, sample_rate: int, window_start: float, window_end: float,
                 weights: dict[str, float] | None = None) -> dict:
    """Return the strongest bounded event and its transparent evidence scores."""
    from scipy.signal import find_peaks

    weights = weights or {"onset_strength": 0.35, "energy_rise": 0.25, "voicing": 0.20,
                          "vocal_band": 0.15, "temporal_prior": 0.05}
    times, features = _features(audio, sample_rate, window_start, window_end)
    if not len(times):
        raise ValueError("empty acoustic-event window")
    position = np.linspace(0.0, 1.0, len(times))
    prior = 1.0 - np.abs(position - 0.5) * 2.0
    score = sum(weights[name] * features[name] for name in ("onset_strength", "energy_rise", "voicing", "vocal_band"))
    score += weights["temporal_prior"] * prior
    peaks, _ = find_peaks(score, distance=max(1, round(0.08 * sample_rate / 160)))
    if not len(peaks):
        peaks = np.array([int(np.argmax(score))])
    ranked = peaks[np.argsort(score[peaks])[::-1]]
    best = int(ranked[0])
    second = float(score[ranked[1]]) if len(ranked) > 1 else 0.0
    end_index = best + 1
    quiet = _unit(features["rms"]) < 0.30
    while end_index < len(times) and end_index - best < round(1.5 * sample_rate / 160):
        if end_index > best + round(0.25 * sample_rate / 160) and np.all(quiet[end_index:min(len(times), end_index + 3)]):
            break
        end_index += 1
    event_end = min(window_end, times[min(end_index, len(times) - 1)] + 160 / sample_rate)
    evidence = {name: round(float(features[name][best]), 6) for name in ("onset_strength", "energy_rise", "voicing", "vocal_band")}
    evidence["temporal_prior"] = round(float(prior[best]), 6)
    confidence = float(np.clip(0.65 * score[best] + 0.35 * max(0.0, score[best] - second), 0.0, 1.0))
    return {"start": round(float(times[best]), 4), "end": round(float(event_end), 4),
            "score": round(float(score[best]), 6), "confidence": round(confidence, 6),
            "evidence": evidence, "competing_score": round(second, 6),
            "window": [window_start, window_end]}
