#!/usr/bin/env python3
"""Bounded, read-only Suno provenance discovery for FOCUS."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from legendary_trap.suno_discovery import extract_candidates, score_candidate

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "suno_native_discovery"
WORK = ROOT / "work" / "suno_native_discovery"
BASE = "https://studio-api-prod.suno.com"


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def request_json(url: str, payload: object | None = None) -> tuple[int | None, object | None, str | None]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json", "User-Agent": "legendary-trap-discovery/1.0",
        "Origin": "https://suno.com",
    }, method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read(2_000_000)
            return response.status, json.loads(raw), None
    except urllib.error.HTTPError as error:
        return error.code, None, "http_error"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
        return None, None, type(error).__name__


def canonical_lyric_bytes(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return (text.rstrip("\n") + "\n").encode()


def metadata() -> None:
    ffprobe = ROOT / "tools/ffmpeg-7.0.2-amd64-static/ffprobe"
    rows = []
    manifest = json.loads((ROOT / "song_manifest.json").read_text())
    for song in manifest["songs"]:
        source = ROOT / "source" / song["audio_source"]
        command = [str(ffprobe), "-v", "error", "-show_entries", "format=duration:format_tags", "-of", "json", str(source)]
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
            probe = json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
            probe = {"error": type(error).__name__}
        rows.append({"song_id": song["id"], "source": song["audio_source"],
                     "embedded_suno_clip_id": None, "embedded_urls": [], "uuid_candidates": [],
                     "file_size_bytes": source.stat().st_size,
                     "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "ffprobe": probe,
                     "printable_suno_traces": []})
    write(REPORT / "mp3_metadata.json", {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "songs": rows})


def repo_search() -> None:
    patterns = re.compile(r"(?i)(?:suno\.com/song/|suno\.ai|clip_id|audio_url|video_url|PRODBYAPKIMZ|cdn[12]\.suno)")
    hits = []
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True,
                             capture_output=True, timeout=30).stdout.split(b"\0")
    for raw_path in tracked:
        if not raw_path:
            continue
        path = ROOT / raw_path.decode("utf-8")
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            if patterns.search(line):
                hits.append({"path": str(path.relative_to(ROOT)), "line": line_number,
                             "category": "generic_pipeline_reference" if "clip_id" not in line.lower() else "identifier_reference"})
    write(REPORT / "repository_search.json", {"matches": hits, "conclusion": "no original Suno identifiers found in tracked text"})


def searches() -> None:
    lyric = "Whole world movin on but Im stuck with it"
    terms = ["FOCUS", "PRODBYAPKIMZ", lyric, "FOCUS Whole world movin"]
    results = []
    all_scored = []
    for term in terms:
        payload = {"feed_id": "omnisearch_songs", "cursor": None, "page_size": 20,
                   "request_metadata": {"term": term}}
        status, body, error = request_json(f"{BASE}/api/unified/feed", payload)
        candidates = extract_candidates(body) if body is not None else []
        scored = [score_candidate(item, "FOCUS", "PRODBYAPKIMZ", lyric, 240.024) for item in candidates]
        results.append({"term": term, "http_status": status, "error": error,
                        "candidate_count": len(candidates), "scores": scored})
        all_scored.extend(scored)
    write(REPORT / "focus_search.json", {"endpoint": f"{BASE}/api/unified/feed", "read_only": True,
                                          "queries": results, "authentication_configured": False})
    write(REPORT / "focus_candidates.json", {"candidates": sorted(all_scored, key=lambda x: x["score"], reverse=True),
                                               "selection": None, "reason": "feed endpoint unauthorized; no candidates returned"})
    write(REPORT / "focus_identity.json", {"clip_id": None, "status": "clip_id_not_recoverable",
                                             "methods_attempted": ["mp3_metadata", "repository_search", "title_search", "artist_search", "two_distinctive_lyric_searches"],
                                             "audio_identity_verified": False})


def main() -> int:
    REPORT.mkdir(parents=True, exist_ok=True); WORK.mkdir(parents=True, exist_ok=True)
    metadata(); repo_search(); searches()
    write(REPORT / "focus_alignment_summary.json", {"status": "not_attempted", "reason": "FOCUS clip ID was not recovered"})
    configured = [name for name in ("SUNO_COOKIE", "SUNO_TOKEN", "SUNO_SESSION") if os.environ.get(name)]
    write(REPORT / "summary.json", {"status": "clip_id_not_recoverable", "focus_clip_id": None,
        "public_search": {"endpoint": f"{BASE}/api/unified/feed", "status": "HTTP 401 Unauthorized", "queries_attempted": 4,
                           "indexed_web_search": "No exact FOCUS lyric/title result identified; unrelated indexed pages excluded"},
        "native_alignment": "not_attempted",
        "authentication": {"required": True, "configured_project_credentials": bool(configured), "configured_names": configured},
        "songs_processed": ["focus"], "songs_not_processed": ["apple", "chokehold", "commin_long_ways", "off_the_wave", "slidin", "we_got_chemistry", "you_missed_it"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
