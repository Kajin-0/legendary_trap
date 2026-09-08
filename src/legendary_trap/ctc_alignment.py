"""Transcript-constrained CTC alignment using Hugging Face Wav2Vec2.

The acoustic model supplies frame posteriors; authoritative text supplies the
target sequence. This module never generates display text and does not depend
on deprecated TorchAudio forced-alignment APIs.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def normalize_ctc(text: str) -> str:
    """Normalize only the alignment view, retaining word boundaries."""
    import re
    text = text.lower().replace("’", "'").replace("`", "'")
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    text = re.sub(r"['’]", "", text)
    return " ".join(text.split())


def _forced_path(log_probs, target_ids: list[int], blank_id: int):
    import torch
    frames, labels = log_probs.shape[0], len(target_ids)
    neg_inf = torch.tensor(-1e9, device=log_probs.device)
    trellis = torch.full((frames + 1, labels + 1), neg_inf, device=log_probs.device)
    trellis[0, 0] = 0.0
    for t in range(frames):
        stay = trellis[t, :] + log_probs[t, blank_id]
        trellis[t + 1, :] = torch.maximum(trellis[t + 1, :], stay)
        if labels:
            change = trellis[t, :-1] + log_probs[t, target_ids]
            trellis[t + 1, 1:] = torch.maximum(trellis[t + 1, 1:], change)
    end = int(torch.argmax(trellis[:, labels]).item())
    if not labels or float(trellis[end, labels]) <= -1e8:
        raise ValueError("CTC trellis could not reach the full target transcript")
    assignments: dict[int, list[tuple[int, float]]] = {}
    t, label = end, labels
    while label > 0 and t > 0:
        stay = float(trellis[t - 1, label] + log_probs[t - 1, blank_id])
        change = float(trellis[t - 1, label - 1] + log_probs[t - 1, target_ids[label - 1]])
        if change >= stay:
            assignments.setdefault(label - 1, []).append((t - 1, float(log_probs[t - 1, target_ids[label - 1]])))
            label -= 1
        t -= 1
    if label:
        raise ValueError("CTC backtracking did not consume the full target transcript")
    return trellis, assignments


def align_audio_window(audio_path: Path, transcript: str, window_start: float = 0.0,
                       window_end: float | None = None,
                       model_name: str = "facebook/wav2vec2-base-960h") -> dict:
    import numpy as np
    import soundfile as sf
    import torch
    from transformers import AutoModelForCTC, AutoProcessor

    started = time.perf_counter()
    audio, sample_rate = sf.read(audio_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sample_rate != 16000:
        import librosa
        audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
        sample_rate = 16000
    start_sample = max(0, round(window_start * sample_rate))
    end_sample = len(audio) if window_end is None else min(len(audio), round(window_end * sample_rate))
    clip = np.asarray(audio[start_sample:end_sample], dtype="float32")
    if len(clip) < sample_rate // 2:
        raise ValueError("CTC window is shorter than 0.5 seconds")
    alignment_text = normalize_ctc(transcript)
    processor = AutoProcessor.from_pretrained(model_name)
    model = AutoModelForCTC.from_pretrained(model_name)
    model.eval()
    inputs = processor(clip, sampling_rate=sample_rate, return_tensors="pt", padding=True)
    with torch.inference_mode():
        logits = model(inputs.input_values).logits[0]
    log_probs = torch.log_softmax(logits, dim=-1)
    vocab = processor.tokenizer.get_vocab()
    vocab = {str(k).lower(): int(v) for k, v in vocab.items()}
    token_text = alignment_text.replace(" ", "|")
    missing = sorted(set(token_text) - set(vocab))
    if missing:
        raise ValueError(f"CTC vocabulary cannot represent normalized characters: {missing}")
    target_ids = [vocab[c] for c in token_text]
    blank_id = int(processor.tokenizer.pad_token_id or 0)
    _, assignments = _forced_path(log_probs, target_ids, blank_id)
    frame_seconds = len(clip) / sample_rate / max(1, logits.shape[0])
    chars = []
    for i, char in enumerate(alignment_text):
        token_pos = i
        if char == " ":
            token_pos = i
        frames = assignments.get(token_pos, [])
        if frames:
            chars.append({"char_index": i, "char": char, "frame_start": min(x[0] for x in frames),
                          "frame_end": max(x[0] for x in frames) + 1,
                          "confidence": float(np.exp(np.mean([x[1] for x in frames])))})
    words = []
    cursor = 0
    for word in alignment_text.split():
        begin = alignment_text.find(word, cursor)
        end = begin + len(word)
        selected = [x for x in chars if begin <= x["char_index"] < end]
        cursor = end
        if selected:
            words.append({"text": word, "start": round(window_start + min(x["frame_start"] for x in selected) * frame_seconds, 4),
                          "end": round(window_start + max(x["frame_end"] for x in selected) * frame_seconds, 4),
                          "confidence": round(float(np.mean([x["confidence"] for x in selected])), 4),
                          "timing_source": "ctc_forced_alignment", "acoustic_support": True})
    return {"model": model_name, "transcript": transcript, "alignment_text": alignment_text,
            "window_start": window_start, "window_end": window_start + len(clip) / sample_rate,
            "frame_count": int(logits.shape[0]), "word_count": len(words), "words": words,
            "mean_word_confidence": float(np.mean([w["confidence"] for w in words])) if words else 0.0,
            "runtime_seconds": time.perf_counter() - started}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("transcript")
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float)
    parser.add_argument("--model", default="facebook/wav2vec2-base-960h")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = align_audio_window(args.audio, args.transcript, args.start, args.end, args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
