"""Reproducible, Apple-only bounded alignment experiments."""
from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

from .alignment import build_alignment, fuse_local_asr
from .asr import transcribe, transcribe_local_windows
from .fine_alignment import refine_boundaries
from .lyrics import parse_lyrics
from .pipeline import ROOT, _duration
from .schema import make_document, write_json
from .validation import validate

LOG = logging.getLogger("legendary_trap.experiment")


def run(config_path: Path) -> dict:
    config = json.loads(config_path.read_text())
    if config.get("song_id", "apple") != "apple":
        raise ValueError("refinement experiments are intentionally limited to Apple")
    name = config["name"]
    out = ROOT / "reports" / "apple_experiments" / name
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "song_manifest.json").read_text())
    song = next(x for x in manifest["songs"] if x["id"] == "apple")
    audio, lyrics = ROOT / config.get("audio_path", song["audio_path"]), ROOT / song["lyrics_path"]
    parsed = parse_lyrics(lyrics, "apple")
    base_path = ROOT / config.get("base_asr", "work/apple/asr-base.en.json")
    if base_path.exists():
        base_asr = json.loads(base_path.read_text())
    else:
        base_asr = transcribe(audio, base_path, model_name=config.get("base_model", "base.en"))
    started = time.perf_counter()
    local = transcribe_local_windows(audio, config["windows"], ROOT / "work" / "apple" / f"local-{name}.json",
                                     model_name=config.get("model", "small.en"), beam_size=config.get("beam_size", 5),
                                     initial_prompts=config.get("initial_prompts"), ffmpeg_bin=ROOT / "tools" / "ffmpeg")
    fused = fuse_local_asr(base_asr, local)
    duration = _duration(audio)
    sections, diag = build_alignment(parsed, fused, duration)
    if config.get("fine_alignment") == "bounded_onset":
        diag["fine_alignment"] = refine_boundaries(sections, audio, float(config.get("fine_radius", 0.18)))
    diag.update({"experiment": name, "runtime_seconds": round(time.perf_counter() - started, 3),
                 "local_asr_runtime_seconds": round(local["runtime_seconds"], 3),
                 "model": config.get("model", "small.en"), "beam_size": config.get("beam_size", 5),
                 "hinted": bool(config.get("initial_prompts"))})
    doc = make_document("apple", {"path": str(audio.relative_to(ROOT)), "duration_seconds": duration}, parsed,
                        sections, {"method": "weighted_monotonic_dp+bounded_local_asr", "fine_alignment": "local_word_timestamps"}, diag)
    write_json(doc, out / "timing.json")
    report = validate(doc, lyrics, song["lyrics_sha256"], duration)
    (out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    summary = {"experiment": name, "song_id": "apple", "valid": report["valid"],
               "runtime_seconds": diag["runtime_seconds"], "local_asr_runtime_seconds": diag["local_asr_runtime_seconds"],
               "token_coverage": diag["token_alignment_coverage"], "line_coverage": diag["line_alignment_coverage"],
               "unresolved_tokens": diag["unresolved_authoritative_tokens"],
               "low_confidence_line_ids": report["low_confidence_line_ids"],
               "validation_failures": report["failures"], "fine_alignment": diag.get("fine_alignment")}
    (out / "diagnostics.json").write_text(json.dumps(diag, indent=2) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("song_id", choices=["apple"])
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(json.dumps(run(args.config), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
