"""Isolated adapter around OpenAI Whisper's teacher-forced attention alignment."""
from __future__ import annotations

import time


def align_known_text(model, text: str, audio, sample_rate: int = 16000, offset: float = 0.0) -> dict:
    """Align authoritative text with Whisper cross-attention inside one clip."""
    import torch
    import whisper
    from whisper.timing import find_alignment

    tokenizer = whisper.tokenizer.get_tokenizer(multilingual=model.is_multilingual, language="en", task="transcribe")
    text_tokens = tokenizer.encode(text)
    audio_tensor = torch.as_tensor(audio, dtype=torch.float32)
    raw_mel = whisper.log_mel_spectrogram(audio_tensor, n_mels=model.dims.n_mels)
    num_frames = raw_mel.shape[-1]
    # Whisper's encoder has a fixed 30-second positional embedding. Preserve
    # the actual local frame count for upstream DTW while right-padding only
    # the tensor presented to the encoder.
    mel = whisper.pad_or_trim(raw_mel, whisper.audio.N_FRAMES).to(model.device)
    started = time.perf_counter()
    timings = find_alignment(model, tokenizer, text_tokens, mel, num_frames)
    words = [{"text": row.word, "start": round(offset + float(row.start), 4),
              "end": round(offset + float(row.end), 4), "probability": float(row.probability),
              "timing_source": "whisper_attention_forced_alignment",
              "transcript_constrained": True, "lexically_recognized": False,
              "acoustic_supported": False} for row in timings]
    return {"text": text, "offset": offset, "duration": len(audio_tensor) / sample_rate,
            "words": words, "runtime_seconds": time.perf_counter() - started,
            "token_count": len(text_tokens), "attention_concentration": None,
            "attention_concentration_note": "OpenAI find_alignment does not expose a calibrated concentration scalar."}
