"""Deterministic parser for authoritative lyric files."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

TOKEN_RE = re.compile(r"[\w]+(?:['’][\w]+)?", re.UNICODE)
SECTION_RE = re.compile(r"^\s*\[(.+?)\]\s*$")


def normalize(text: str) -> str:
    """Return alignment-only text; never use this as display text."""
    text = text.replace("’", "'").replace("`", "'").lower()
    return " ".join(TOKEN_RE.findall(text))


def tokens(text: str) -> list[str]:
    return normalize(text).split() if normalize(text) else []


@dataclass
class LyricLine:
    line_id: str
    section_id: str
    source_line: int
    original_text: str
    lead_text: str
    adlibs: list[str] = field(default_factory=list)
    normalized_text: str = ""
    tokens: list[str] = field(default_factory=list)


@dataclass
class LyricSection:
    section_id: str
    label: str
    source_start_line: int
    lines: list[LyricLine] = field(default_factory=list)


@dataclass
class ParsedLyrics:
    song_id: str
    path: str
    sha256: str
    sections: list[LyricSection]

    @property
    def lines(self) -> list[LyricLine]:
        return [line for section in self.sections for line in section.lines]

    @property
    def token_count(self) -> int:
        return sum(len(line.tokens) for line in self.lines)

    def to_dict(self) -> dict:
        return {
            "song_id": self.song_id,
            "path": self.path,
            "sha256": self.sha256,
            "sections": [
                {"section_id": s.section_id, "label": s.label, "source_start_line": s.source_start_line,
                 "lines": [asdict(line) for line in s.lines]}
                for s in self.sections
            ],
        }


def _split_parentheticals(text: str) -> tuple[str, list[str]]:
    adlibs = re.findall(r"\(([^()]*)\)", text)
    lead = re.sub(r"\s*\([^()]*\)", "", text).strip()
    return lead, [a.strip() for a in adlibs if a.strip()]


def parse_lyrics(path: Path, song_id: str) -> ParsedLyrics:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    digest = hashlib.sha256((text.rstrip("\n") + "\n").encode("utf-8")).hexdigest()
    sections: list[LyricSection] = []
    current: LyricSection | None = None
    section_index = 0
    for number, raw_line in enumerate(text.splitlines(), 1):
        marker = SECTION_RE.match(raw_line)
        if marker:
            section_index += 1
            current = LyricSection(f"section_{section_index:03d}", marker.group(1), number)
            sections.append(current)
            continue
        if not raw_line.strip():
            continue
        if current is None:
            section_index += 1
            current = LyricSection(f"section_{section_index:03d}", "Unsectioned", number)
            sections.append(current)
        lead, adlibs = _split_parentheticals(raw_line)
        current.lines.append(LyricLine(
            line_id=f"{current.section_id}_line_{len(current.lines)+1:03d}",
            section_id=current.section_id, source_line=number, original_text=raw_line,
            lead_text=lead, adlibs=adlibs, normalized_text=normalize(lead), tokens=tokens(lead),
        ))
    return ParsedLyrics(song_id, str(path), digest, sections)
