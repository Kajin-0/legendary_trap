"""Explicit, non-fabricating artist identity lockup configuration."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ArtistLockup:
    name: str | None
    pfp_path: Path | None
    asset_status: str
    artist_ids: tuple[str, ...] = ()
    pfp_paths: tuple[Path, ...] = ()


def artist_lockup_for_song(song_id: str) -> ArtistLockup:
    """Return a validated lockup, never a fabricated identity or placeholder."""
    songs_path = ROOT / "configs" / "songs.json"
    artists_path = ROOT / "configs" / "artists.json"
    if not songs_path.is_file() or not artists_path.is_file():
        return ArtistLockup(None, None, "missing_artist_catalog")
    songs = json.loads(songs_path.read_text(encoding="utf-8"))
    artists = json.loads(artists_path.read_text(encoding="utf-8"))["artists"]
    artist_ids = tuple(songs["songs"].get(song_id, {}).get("artists", []))
    if not artist_ids:
        return ArtistLockup(None, None, "missing_authoritative_artist_metadata")
    records = [artists.get(artist_id) for artist_id in artist_ids]
    if any(not record or not record.get("display_name") for record in records):
        return ArtistLockup(None, None, "missing_authoritative_artist_name", artist_ids)
    names = tuple(record["display_name"] for record in records)
    name = " × ".join(names)
    pfp_paths = tuple(ROOT / record["pfp"] for record in records if record.get("pfp"))
    if len(pfp_paths) != len(records) or any(not path.is_file() for path in pfp_paths):
        return ArtistLockup(name, None, "missing_repo_local_pfp", artist_ids, pfp_paths)
    return ArtistLockup(name, pfp_paths[0] if pfp_paths else None, "ready", artist_ids, pfp_paths)


def format_artist_names(names: tuple[str, ...] | list[str]) -> str:
    """Format one or more verified names for the compact lockup."""
    return " × ".join(name for name in names if name)
