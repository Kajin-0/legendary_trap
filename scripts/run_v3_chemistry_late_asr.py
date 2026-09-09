"""Run one unhinted, bounded late-song ASR pass for the v3 audit."""
from __future__ import annotations

import json
from pathlib import Path

from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "distil-whisper/distil-large-v3-ct2"
START = 205.0
END = 249.24


def main() -> int:
    audio = ROOT / "source" / "we got chemistry.mp3"
    clip = ROOT / "work" / "we_got_chemistry" / "large_whisper" / "v3_late.wav"
    clip.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = ROOT / "tools" / "ffmpeg-7.0.2-amd64-static" / "ffmpeg"
    import subprocess
    subprocess.run([str(ffmpeg), "-y", "-v", "error", "-ss", str(START), "-to", str(END),
                    "-i", str(audio), "-ac", "1", "-ar", "16000", str(clip)],
                   check=True, timeout=60)
    model = WhisperModel(MODEL_ID, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(clip), language="en", beam_size=5, word_timestamps=True,
        condition_on_previous_text=False, vad_filter=False, temperature=0.0,
        initial_prompt=None,
    )
    rows = []
    for segment in segments:
        words = []
        for word in segment.words or []:
            if word.word.strip():
                words.append({"text": word.word.strip(), "start": round(START + word.start, 4),
                              "end": round(START + word.end, 4), "probability": word.probability})
        rows.append({"start": round(START + segment.start, 4),
                     "end": round(START + segment.end, 4), "text": segment.text,
                     "avg_logprob": segment.avg_logprob,
                     "no_speech_prob": segment.no_speech_prob, "words": words})
    out = ROOT / "reports" / "v3_individual_audit" / "chemistry_late_asr.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"model": MODEL_ID, "window": [START, END],
                               "language_probability": info.language_probability,
                               "segments": rows}, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(out.relative_to(ROOT)), "segments": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
