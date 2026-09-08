"""Disposable acoustic locator based on faster-whisper."""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ASRWord:
    text: str
    start: float
    end: float
    probability: float


@dataclass
class ASRSegment:
    start: float
    end: float
    text: str
    avg_logprob: float | None
    no_speech_prob: float | None
    words: list[ASRWord]


def transcribe(audio: Path, out_path: Path, model_name: str = "tiny.en", threads: int = 8) -> dict:
    from faster_whisper import WhisperModel
    started = time.perf_counter()
    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=threads)
    segments, info = model.transcribe(
        str(audio), language="en", beam_size=3, best_of=1, temperature=0,
        # Music often defeats the generic Silero VAD; keep all audio and let
        # the acoustic word timestamps/DP decide what is usable.
        vad_filter=False, word_timestamps=True, condition_on_previous_text=False,
    )
    rows: list[ASRSegment] = []
    for seg in segments:
        words = [ASRWord(w.word.strip(), float(w.start), float(w.end), float(w.probability))
                 for w in (seg.words or []) if w.word.strip()]
        rows.append(ASRSegment(float(seg.start), float(seg.end), seg.text.strip(),
                               getattr(seg, "avg_logprob", None), getattr(seg, "no_speech_prob", None), words))
    result = {"model": model_name, "device": "cpu", "compute_type": "int8",
              "language": info.language, "language_probability": info.language_probability,
              "duration": info.duration, "segments": [asdict(s) for s in rows],
              "runtime_seconds": time.perf_counter() - started}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def transcribe_local_windows(audio: Path, windows: list[dict], out_path: Path,
                             model_name: str = "small.en", beam_size: int = 5,
                             initial_prompts: dict[str, str] | None = None,
                             ffmpeg_bin: Path | None = None, threads: int = 8) -> dict:
    """Transcribe only bounded windows and return timestamps in song coordinates."""
    from faster_whisper import WhisperModel
    ffmpeg_bin = ffmpeg_bin or Path("ffmpeg")
    started = time.perf_counter()
    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=threads)
    rows = []
    scratch = out_path.parent / "local_windows"
    scratch.mkdir(parents=True, exist_ok=True)
    for window in windows:
        clip = scratch / f"{window['window_id']}.wav"
        subprocess.run([str(ffmpeg_bin), "-y", "-v", "error", "-ss", str(window["start"]),
                        "-to", str(window["end"]), "-i", str(audio), "-ac", "1", "-ar", "16000", str(clip)],
                       check=True)
        segments, _ = model.transcribe(
            str(clip), language="en", beam_size=beam_size, best_of=1, temperature=0,
            vad_filter=False, word_timestamps=True, condition_on_previous_text=False,
            initial_prompt=(initial_prompts or {}).get(window["window_id"]),
        )
        clip_segments = []
        for segment in segments:
            words = [{"text": w.word.strip(), "start": round(w.start + window["start"], 4),
                      "end": round(w.end + window["start"], 4), "probability": w.probability}
                     for w in (segment.words or []) if w.word.strip()]
            clip_segments.append({"start": segment.start + window["start"],
                                  "end": segment.end + window["start"], "text": segment.text.strip(),
                                  "words": words})
        rows.append({"window": window, "segments": clip_segments})
    result = {"model": model_name, "compute_type": "int8", "device": "cpu", "beam_size": beam_size,
              "hinted": bool(initial_prompts), "windows": rows,
              "runtime_seconds": time.perf_counter() - started}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
