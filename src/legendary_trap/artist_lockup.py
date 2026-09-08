"""Explicit, non-fabricating artist identity lockup configuration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ArtistLockup:
    name: str | None
    pfp_path: Path | None
    asset_status: str


# No authoritative artist identity or profile asset is currently present.
ARTIST_METADATA: dict[str, dict[str, str]] = {}


def artist_lockup_for_song(song_id: str) -> ArtistLockup:
    """Return a validated lockup, never a fabricated identity or placeholder."""
    metadata = ARTIST_METADATA.get(song_id)
    if not metadata:
        return ArtistLockup(None, None, "missing_authoritative_artist_metadata")
    name = metadata.get("name")
    raw_pfp = metadata.get("pfp")
    pfp = ROOT / raw_pfp if raw_pfp else None
    if not name:
        return ArtistLockup(None, None, "missing_authoritative_artist_name")
    if pfp is None or not pfp.is_file():
        return ArtistLockup(name, None, "missing_repo_local_pfp")
    return ArtistLockup(name, pfp, "ready")
