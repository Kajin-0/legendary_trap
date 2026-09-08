#!/usr/bin/env python3
"""Import tracked source MP3s into canonical runtime paths.

The repository transports original MP3 files directly under source/. Authoritative
lyrics live under input/lyrics/ and are fingerprinted in song_manifest.json.
This script verifies lyric integrity, verifies every expected source MP3 exists,
and copies audio into canonical gitignored input/audio/ filenames for processing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "song_manifest.json"
SOURCE_DIR = ROOT / "source"


def canonical_lyric_bytes(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return (text.rstrip("\n") + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--overwrite-audio",
        action="store_true",
        help="Replace already-imported canonical audio files.",
    )
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    songs = manifest["songs"]

    (ROOT / "input" / "audio").mkdir(parents=True, exist_ok=True)
    (ROOT / "work").mkdir(exist_ok=True)
    (ROOT / "output").mkdir(exist_ok=True)

    failures: list[str] = []

    for song in songs:
        song_id = song["id"]
        source_audio = SOURCE_DIR / song["audio_source"]
        audio_dest = ROOT / song["audio_path"]
        lyric_path = ROOT / song["lyrics_path"]

        if not source_audio.is_file():
            failures.append(
                f"{song_id}: missing tracked source audio: {source_audio.relative_to(ROOT)}"
            )
            continue
        if source_audio.stat().st_size <= 0:
            failures.append(f"{song_id}: source audio is empty: {source_audio.relative_to(ROOT)}")
            continue

        if not lyric_path.is_file():
            failures.append(f"{song_id}: authoritative lyric missing: {lyric_path.relative_to(ROOT)}")
            continue

        digest = sha256_bytes(canonical_lyric_bytes(lyric_path))
        if digest != song["lyrics_sha256"]:
            failures.append(
                f"{song_id}: authoritative lyric fingerprint mismatch; "
                f"expected {song['lyrics_sha256']}, got {digest}"
            )
            continue

        if audio_dest.exists() and not args.overwrite_audio:
            print(f"SKIP  {song_id:20s} {audio_dest.relative_to(ROOT)} already exists")
        else:
            audio_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_audio, audio_dest)
            print(
                f"AUDIO {song_id:20s} {source_audio.relative_to(ROOT)} "
                f"-> {audio_dest.relative_to(ROOT)}"
            )

        print(f"LYRIC {song_id:20s} SHA-256 verified")

    if failures:
        print("\nImport failed validation:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"\nValidated and imported {len(songs)} songs from source/.")
    print("Authoritative lyrics were verified and never rewritten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
