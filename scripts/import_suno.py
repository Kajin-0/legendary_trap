#!/usr/bin/env python3
"""Import song audio from GitHub-transported source archive parts.

The repository contains authoritative lyric text plus split source/Suno.zip.part-*
transport artifacts (each below GitHub web upload's 25 MB limit). This script
verifies the parts, reconstructs work/Suno.zip, extracts only source audio,
verifies ZIP lyrics exactly match committed authoritative lyrics, and ignores
legacy ASS files and image assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "song_manifest.json"
ARCHIVE_MANIFEST_PATH = ROOT / "source" / "archive_manifest.json"
DEFAULT_ARCHIVE = ROOT / "source" / "Suno.zip"
DEFAULT_PART_GLOB = "Suno.zip.part-*"
RECONSTRUCTED_ARCHIVE = ROOT / "work" / "Suno.zip"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


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


def reconstruct_from_parts() -> Path:
    if not ARCHIVE_MANIFEST_PATH.is_file():
        raise RuntimeError(f"Missing archive manifest: {ARCHIVE_MANIFEST_PATH}")

    meta = json.loads(ARCHIVE_MANIFEST_PATH.read_text(encoding="utf-8"))
    source_dir = ROOT / "source"
    expected_parts = meta["parts"]

    for item in expected_parts:
        part = source_dir / item["name"]
        if not part.is_file():
            raise RuntimeError(f"Missing archive part: {part.relative_to(ROOT)}")
        actual_size = part.stat().st_size
        if actual_size != item["size_bytes"]:
            raise RuntimeError(
                f"Size mismatch for {part.name}: expected {item['size_bytes']}, got {actual_size}"
            )
        actual_hash = sha256_file(part)
        if actual_hash != item["sha256"]:
            raise RuntimeError(
                f"SHA-256 mismatch for {part.name}: expected {item['sha256']}, got {actual_hash}"
            )

    RECONSTRUCTED_ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with RECONSTRUCTED_ARCHIVE.open("wb") as out:
        for item in expected_parts:
            with (source_dir / item["name"]).open("rb") as src:
                for block in iter(lambda: src.read(1024 * 1024), b""):
                    out.write(block)

    expected_size = meta["archive"]["size_bytes"]
    actual_size = RECONSTRUCTED_ARCHIVE.stat().st_size
    if actual_size != expected_size:
        raise RuntimeError(
            f"Reconstructed archive size mismatch: expected {expected_size}, got {actual_size}"
        )

    expected_hash = meta["archive"]["sha256"]
    actual_hash = sha256_file(RECONSTRUCTED_ARCHIVE)
    if actual_hash != expected_hash:
        raise RuntimeError(
            f"Reconstructed archive SHA-256 mismatch: expected {expected_hash}, got {actual_hash}"
        )

    print(
        f"REBUILD {RECONSTRUCTED_ARCHIVE.relative_to(ROOT)} from "
        f"{len(expected_parts)} verified parts"
    )
    return RECONSTRUCTED_ARCHIVE


def resolve_archive(explicit_archive: Path | None) -> Path:
    if explicit_archive is not None:
        archive = explicit_archive.expanduser().resolve()
        if not archive.is_file():
            raise RuntimeError(f"Archive not found: {archive}")
        return archive

    if DEFAULT_ARCHIVE.is_file():
        return DEFAULT_ARCHIVE

    parts = sorted((ROOT / "source").glob(DEFAULT_PART_GLOB))
    if parts:
        return reconstruct_from_parts()

    raise RuntimeError(
        "No source archive found. Upload source/Suno.zip.part-000 and "
        "source/Suno.zip.part-001 to GitHub, then git pull on the VPS."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "archive",
        nargs="?",
        type=Path,
        default=None,
        help=(
            "Optional direct path to Suno.zip. If omitted, use source/Suno.zip when present, "
            "otherwise reconstruct from source/Suno.zip.part-*"
        ),
    )
    parser.add_argument(
        "--overwrite-audio",
        action="store_true",
        help="Replace already-imported canonical audio files.",
    )
    args = parser.parse_args()

    try:
        archive = resolve_archive(args.archive)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    songs = manifest["songs"]

    audio_dir = ROOT / "input" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    (ROOT / "work").mkdir(exist_ok=True)
    (ROOT / "output").mkdir(exist_ok=True)

    failures: list[str] = []

    try:
        zf_context = zipfile.ZipFile(archive)
    except zipfile.BadZipFile:
        print(f"ERROR: not a valid ZIP archive: {archive}", file=sys.stderr)
        return 2

    with zf_context as zf:
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
