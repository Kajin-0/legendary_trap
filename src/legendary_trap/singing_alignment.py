"""Adapter for the isolated ``schufo/lyrics-aligner`` singing model.

The upstream model is transcript constrained. This adapter keeps the lyric
text authoritative, exposes phoneme/word provenance, and computes diagnostics
from the model score path and its estimated vocal magnitude. It deliberately
does not convert every forced position into acoustic evidence.
"""
from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np

UPSTREAM = Path(__file__).resolve().parents[2] / "third_party" / "lyrics-aligner"
MODEL_PATH = UPSTREAM / "model_parameters.pth"
PHONEME_MAP_PATH = UPSTREAM / "files" / "phoneme2idx.pickle"
_MODEL_CACHE = None


def _clean_word(word: str) -> str:
    return (word.lower().replace("’", "'").replace("`", "'").strip("'\".,!?;:()[]{}"))


def _strip_stress(phone: str) -> str:
    return "".join(ch for ch in phone.upper() if not ch.isdigit())


def words_to_arpabet(words: list[str]) -> dict:
    """Map words to ARPAbet using CMUdict, then g2p-en for OOV words."""
    import cmudict

    dictionary = cmudict.dict()
    fallback = None
    output = []
    for original in words:
        clean = _clean_word(original)
        pronunciations = dictionary.get(clean) or dictionary.get(clean.replace("'", ""))
        source = "cmudict"
        if pronunciations:
            phones = [_strip_stress(x) for x in pronunciations[0]]
        else:
            if fallback is None:
                from g2p_en import G2p

                fallback = G2p()
            phones = [_strip_stress(x) for x in fallback(clean) if x.isalpha()]
            source = "g2p-en"
        output.append({"original_word": original, "normalized_word": clean,
                       "phonemes": phones, "g2p_source": source,
                       "g2p_fallback": source != "cmudict"})
    return {"words": output, "oov_words": [x["original_word"] for x in output if x["g2p_fallback"]]}


def _load_upstream():
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE
    if str(UPSTREAM) not in sys.path:
        sys.path.insert(0, str(UPSTREAM))
    import model as upstream_model

    with PHONEME_MAP_PATH.open("rb") as handle:
        phoneme_to_index = pickle.load(handle)
    aligner = upstream_model.InformedOpenUnmix3().eval()
    aligner.load_state_dict(__import__("torch").load(MODEL_PATH, map_location="cpu", weights_only=False))
    _MODEL_CACHE = (aligner, phoneme_to_index)
    return _MODEL_CACHE


def align_window(audio_path: Path, words: list[str], window_start: float,
                 window_end: float, vad_threshold: float = 0.0) -> dict:
    """Run the singing aligner over one bounded window and return evidence."""
    import librosa
    import soundfile as sf
    import torch

    started = time.perf_counter()
    audio, sample_rate = sf.read(audio_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sample_rate != 16000:
        audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
        sample_rate = 16000
    lo, hi = round(window_start * sample_rate), round(window_end * sample_rate)
    clip = np.asarray(audio[lo:hi], dtype="float32")
    g2p = words_to_arpabet(words)
    phonemes = [">"]
    word_ranges = []
    for item in g2p["words"]:
        begin = len(phonemes)
        phonemes.extend(item["phonemes"])
        phonemes.append(">")
        word_ranges.append((begin, len(phonemes) - 1))
    aligner, mapping = _load_upstream()
    unknown = sorted(set(phonemes) - set(mapping))
    if unknown:
        raise ValueError(f"phonemes absent from upstream vocabulary: {unknown}")
    indices = torch.tensor([[mapping[p] for p in phonemes]], dtype=torch.float32)
    signal = torch.tensor(clip, dtype=torch.float32)[None, None, :]
    with torch.inference_mode():
        voice_estimate, _, scores = aligner((signal, indices))
    score_array = scores[0].cpu().numpy()
    voice_array = voice_estimate[:, 0, 0, :].cpu().numpy().sum(axis=1)
    # The upstream DTW path uses only monotonic transitions. Import its small
    # reference implementation without copying it into the production package.
    if str(UPSTREAM) not in sys.path:
        sys.path.insert(0, str(UPSTREAM))
    import align as upstream_align

    path = upstream_align.optimal_alignment_path(scores.cpu())
    frame_indices = np.argmax(path, axis=1)
    hop_seconds = 256 / 16000
    phoneme_entries = []
    for pidx, symbol in enumerate(phonemes):
        frames = np.flatnonzero(frame_indices == pidx)
        if len(frames) == 0:
            phoneme_entries.append({"symbol": symbol, "start": None, "end": None,
                                    "support": 0.0, "frame_count": 0})
            continue
        scores_here = score_array[frames, pidx]
        # Softmax over the transcript phoneme positions is a relative diagnostic,
        # not a calibrated probability. Vocal magnitude is retained separately.
        shifted = scores_here - score_array[frames].max(axis=1)
        support = float(np.mean(1 / (1 + np.exp(-shifted))))
        phoneme_entries.append({"symbol": symbol,
                                "start": round(window_start + int(frames[0]) * hop_seconds, 4),
                                "end": round(window_start + int(frames[-1] + 1) * hop_seconds, 4),
                                "support": round(support, 6), "frame_count": len(frames)})
    vocal_p95 = float(np.percentile(voice_array, 95)) if len(voice_array) else 0.0
    vocal_median = float(np.median(voice_array)) if len(voice_array) else 0.0
    word_entries = []
    for word, (first, last) in zip(words, word_ranges):
        parts = [x for x in phoneme_entries[first:last] if x["start"] is not None]
        mean_support = float(np.mean([x["support"] for x in parts])) if parts else 0.0
        word_entries.append({"text": word, "start": parts[0]["start"] if parts else None,
                             "end": parts[-1]["end"] if parts else None,
                             "phoneme_count": len(parts), "supported_phonemes": sum(x["support"] >= 0.5 for x in parts),
                             "phoneme_support": round(mean_support, 6),
                             "vocal_activity_ratio": round(vocal_median / vocal_p95, 6) if vocal_p95 else 0.0,
                             "timing_source": "singing_forced_alignment",
                             "acoustic_support": bool(parts and mean_support >= 0.5),
                             "confidence": round(mean_support, 6)})
    return {"window_start": window_start, "window_end": window_end, "words": word_entries,
            "phonemes": phoneme_entries, "phoneme_count": len(phonemes),
            "supported_phonemes": sum(x["support"] >= 0.5 for x in phoneme_entries),
            "phoneme_acoustic_coverage": sum(x["support"] >= 0.5 for x in phoneme_entries) / len(phonemes),
            "vocal_magnitude_median": vocal_median, "vocal_magnitude_p95": vocal_p95,
            "vad_threshold": vad_threshold, "model_runtime_seconds": time.perf_counter() - started,
            "g2p": g2p}
