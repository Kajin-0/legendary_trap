#!/usr/bin/env python3
"""Import song audio from the repository transport archive.

The repository contains authoritative lyric text plus a tracked source/Suno.zip
transport artifact. This script extracts only source audio, verifies that the ZIP
lyrics exactly match the committed authoritative lyrics, and ignores legacy ASS
files and image assets.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "song_manifest.json"
DEFAULT_ARCHIVE = ROOT / "source" / "Suno.zip"


def normalize_text(data: bytes) -> str:
    """Decode UTF-8 text and normalize only newline representation."""
    return data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def find_member(zf: zipfile.ZipFile, basename: str) -> str:
    matches = [name for name in zf.namelist() if Path(name).name == basename]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one archive member named {basename!r}; found {matches!r}"
        )
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "archive",
        nargs="?",
        type=Path,
        default=DEFAULT_ARCHIVE,
        help="Path to Suno.zip (default: source/Suno.zip)",
    )
    parser.add_argument(
        "--overwrite-audio",
        action="store_true",
        help="Replace already-imported canonical audio files.",
    )
    args = parser.parse_args()

    archive = args.archive.expanduser().resolve()
    if not archive.is_file():
        print(f"ERROR: archive not found: {archive}", file=sys.stderr)
        print(
            "Upload Suno.zip to source/Suno.zip in GitHub, then git pull on the VPS.",
            file=sys.stderr,
        )
        return 2

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    songs = manifest["songs"]

    audio_dir = ROOT / "input" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    (ROOT / "work").mkdir(exist_ok=True)
    (ROOT / "output").mkdir(exist_ok=True)

    failures: list[str] = []

    with zipfile.ZipFile(archive) as zf:
        for song in songs:
            song_id = song["id"]
            try:
                audio_member = find_member(zf, song["audio_source"])
                lyric_member = find_member(zf, song["lyrics_source"])
            except RuntimeError as exc:
                failures.append(f"{song_id}: {exc}")
                continue

            audio_dest = ROOT / song["audio_path"]
            lyric_dest = ROOT / song["lyrics_path"]

            if not lyric_dest.is_file():
                failures.append(f"{song_id}: committed lyric missing: {lyric_dest}")
                continue

            archive_lyric = normalize_text(zf.read(lyric_member)).rstrip("\n")
            repo_lyric = normalize_text(lyric_dest.read_bytes()).rstrip("\n")
            if archive_lyric != repo_lyric:
                failures.append(
                    f"{song_id}: archive lyric differs from committed authoritative lyric"
                )
                continue

            if audio_dest.exists() and not args.overwrite_audio:
                print(f"SKIP  {song_id:20s} {audio_dest.relative_to(ROOT)} already exists")
            else:
                audio_dest.parent.mkdir(parents=True, exist_ok=True)
                audio_dest.write_bytes(zf.read(audio_member))
                print(f"AUDIO {song_id:20s} -> {audio_dest.relative_to(ROOT)}")

            print(f"LYRIC {song_id:20s} verified")

    if failures:
        print("\nImport failed validation:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"\nValidated and imported {len(songs)} songs.")
    print("Legacy ASS/image files were intentionally not imported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
