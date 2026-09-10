"""Metadata and offset planning for the future single-file compilation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SONGS_CONFIG = ROOT / "configs" / "songs.json"
ARTISTS_CONFIG = ROOT / "configs" / "artists.json"


@dataclass(frozen=True)
class TrackPlan:
    song_id: str
    title: str
    artists: tuple[str, ...]
    local_start: float
    master_start: float


def load_catalog() -> tuple[dict, dict]:
    """Load auditable song and artist metadata without touching timing JSON."""
    songs = json.loads(SONGS_CONFIG.read_text(encoding="utf-8"))
    artists = json.loads(ARTISTS_CONFIG.read_text(encoding="utf-8"))
    order = songs["track_order"]
    # Metadata may include prepared songs that are intentionally not yet in
    # the production playlist.  The ordered playlist must remain explicit,
    # while every ordered item must have metadata.
    if len(order) != len(set(order)) or not set(order).issubset(songs["songs"]):
        raise ValueError("track_order contains missing or duplicate song metadata")
    return songs, artists


def build_track_plan(durations: dict[str, float], transition_seconds: float = 0.0) -> list[TrackPlan]:
    """Calculate cumulative master offsets from actual rendered durations.

    `transition_seconds` is an explicit future composition parameter. Canonical
    per-song timing remains local; this function only produces runtime offsets.
    """
    if transition_seconds < 0:
        raise ValueError("transition_seconds must be non-negative")
    songs, _artists = load_catalog()
    cursor = 0.0
    plans: list[TrackPlan] = []
    for song_id in songs["track_order"]:
        if song_id not in durations or durations[song_id] <= 0:
            raise ValueError(f"missing positive duration for {song_id}")
        metadata = songs["songs"][song_id]
        plans.append(TrackPlan(song_id, metadata["title"], tuple(metadata["artists"]), 0.0, cursor))
        cursor += float(durations[song_id]) + transition_seconds
    return plans


def chapter_rows(plans: list[TrackPlan]) -> list[dict[str, object]]:
    """Return chapter-ready rows; timestamps are generated only from real plans."""
    return [{"song_id": plan.song_id, "title": plan.title, "start_seconds": plan.master_start}
            for plan in plans]
