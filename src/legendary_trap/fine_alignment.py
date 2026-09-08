"""CPU-feasible bounded boundary refinement.

This is deliberately conservative: it searches only near already-associated
word boundaries and keeps the ASR word spans as the timing authority for words.
It is not a substitute for a phoneme CTC aligner.
"""
from __future__ import annotations

from pathlib import Path


def refine_boundaries(sections: list[dict], audio_path: Path, radius: float = 0.18) -> dict:
    import librosa
    y, sr = librosa.load(str(audio_path), sr=16000, mono=True)
    strength = librosa.onset.onset_strength(y=y, sr=sr, hop_length=256)
    frame_times = librosa.frames_to_time(range(len(strength)), sr=sr, hop_length=256)
    shifts = []
    refined = 0
    for block in sections:
        for row in block["rows"]:
            if not row["words"]:
                row["acoustic_start"], row["acoustic_end"] = row["start"], row["end"]
                continue
            first, last = row["words"][0], row["words"][-1]
            def peak(center: float) -> float:
                candidates = [i for i, t in enumerate(frame_times) if abs(float(t) - center) <= radius]
                return float(frame_times[max(candidates, key=lambda i: strength[i])]) if candidates else center
            row["acoustic_start"], row["acoustic_end"] = peak(first.start), peak(last.end)
            shifts.extend([row["acoustic_start"] - first.start, row["acoustic_end"] - last.end])
            refined += 1
    return {"method": "bounded_rms_onset_peak", "radius_seconds": radius,
            "refined_line_count": refined, "median_boundary_shift_seconds": float(__import__("statistics").median(shifts)) if shifts else 0.0}
