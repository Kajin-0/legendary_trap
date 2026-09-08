"""CLI orchestration for one-song pilot runs."""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import time
from pathlib import Path

from .alignment import build_alignment
from .asr import transcribe
from .exporters import write_ass, write_srt, write_vtt
from .lyrics import parse_lyrics
from .schema import make_document, write_json
from .validation import validate

LOG = logging.getLogger("legendary_trap")
ROOT = Path(__file__).resolve().parents[2]


def _duration(path: Path) -> float:
    probe = ROOT / "tools" / "ffprobe"
    result = subprocess.run([str(probe), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], check=True, capture_output=True, text=True)
    return float(result.stdout.strip())


def run(song_id: str, model: str, timeout_seconds: int) -> dict:
    manifest = json.loads((ROOT / "song_manifest.json").read_text())
    song = next(s for s in manifest["songs"] if s["id"] == song_id)
    audio = ROOT / song["audio_path"]; lyrics = ROOT / song["lyrics_path"]
    work = ROOT / "work" / song_id; output = ROOT / "output" / song_id
    work.mkdir(parents=True, exist_ok=True); output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter(); parse_started = time.perf_counter(); parsed = parse_lyrics(lyrics, song_id)
    parse_runtime = time.perf_counter() - parse_started
    (work / "lyrics.parsed.json").write_text(json.dumps(parsed.to_dict(), indent=2, ensure_ascii=False) + "\n")
    duration = _duration(audio)
    asr_path = work / f"asr-{model.replace('/', '_')}.json"
    cached_asr = json.loads(asr_path.read_text()) if asr_path.exists() else None
    if not cached_asr or not cached_asr.get("segments"):
        LOG.info("ASR model=%s audio=%s", model, audio)
        asr = transcribe(audio, asr_path, model_name=model)
    else:
        asr = cached_asr
    sections, diag = build_alignment(parsed, asr, duration)
    all_rows = [row for block in sections for row in block["rows"]]
    lead_rows = [row for row in all_rows if row["total_tokens"] > 0]
    diag.update({"line_acoustic_coverage": sum(row["matched_tokens"] > 0 for row in all_rows) / len(all_rows) if all_rows else 1.0,
                 "lead_line_acoustic_coverage": sum(row["matched_tokens"] > 0 for row in lead_rows) / len(lead_rows) if lead_rows else 1.0,
                 "adlib_only_line_count": len(all_rows) - len(lead_rows),
                 "token_acoustic_coverage": diag["token_alignment_coverage"]})
    asr_runtime = asr.get("runtime_seconds", 0.0) if not cached_asr else 0.0
    diag.update({"audio_duration_seconds": duration, "authoritative_section_count": len(parsed.sections),
                 "authoritative_line_count": len(parsed.lines), "authoritative_token_count": parsed.token_count,
                 "model": model, "device": "cpu", "stage_runtime_seconds": round(time.perf_counter()-started, 3),
                 "stage_runtimes_seconds": {"parse": round(parse_runtime, 4),
                                            "asr": round(asr_runtime, 3),
                                            "alignment_and_export": round(max(0.0, time.perf_counter()-started-parse_runtime-asr_runtime), 3)},
                 "asr_cached": bool(cached_asr)})
    doc = make_document(song_id, {"path": str(audio.relative_to(ROOT)), "duration_seconds": duration}, parsed,
                        sections, {"method": "weighted_monotonic_dp", "fine_alignment": "word_timestamp_bounded_windows"}, diag)
    timing = output / "timing.json"; write_json(doc, timing)
    report = validate(doc, lyrics, song["lyrics_sha256"], duration)
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    write_ass(doc, output / f"{song_id}.ass", karaoke=False)
    write_ass(doc, output / f"{song_id}.karaoke.ass", karaoke=True)
    write_srt(doc, output / f"{song_id}.srt")
    write_vtt(doc, output / f"{song_id}.vtt")
    summary = {"song_id": song_id, "valid": report["valid"], "diagnostics": diag, "validation": report,
               "artifacts": [str(p.relative_to(ROOT)) for p in sorted(output.iterdir())]}
    (output / "diagnostics.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Align one authoritative lyric file to its song")
    parser.add_argument("song_id", default="apple", nargs="?")
    parser.add_argument("--model", default="tiny.en")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(levelname)s %(message)s")
    result = run(args.song_id, args.model, args.timeout)
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
