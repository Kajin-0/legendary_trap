from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "song_manifest.json").read_text(encoding="utf-8"))


def canonical_bytes(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return (text.rstrip("\n") + "\n").encode("utf-8")


def test_song_ids_are_unique() -> None:
    ids = [song["id"] for song in MANIFEST["songs"]]
    assert len(ids) == len(set(ids))
    assert len(ids) == 8


def test_authoritative_lyrics_exist_and_match_fingerprints() -> None:
    for song in MANIFEST["songs"]:
        path = ROOT / song["lyrics_path"]
        assert path.is_file(), f"missing authoritative lyric: {path}"
        digest = hashlib.sha256(canonical_bytes(path)).hexdigest()
        assert digest == song["lyrics_sha256"], (
            f"authoritative lyric changed for {song['id']}: "
            f"expected {song['lyrics_sha256']}, got {digest}"
        )


def test_manifest_paths_stay_inside_expected_directories() -> None:
    for song in MANIFEST["songs"]:
        assert song["lyrics_path"].startswith("input/lyrics/")
        assert song["audio_path"].startswith("input/audio/")
        assert ".." not in Path(song["lyrics_path"]).parts
        assert ".." not in Path(song["audio_path"]).parts
