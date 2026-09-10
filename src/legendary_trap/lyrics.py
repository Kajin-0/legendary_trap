"""Deterministic parser for authoritative lyric files."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

TOKEN_RE = re.compile(r"[\w]+(?:['’][\w]+)?", re.UNICODE)
SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
MALFORMED_SECTION_RE = re.compile(r"^\s*\[([^\[\]]+)\s*$")
KNOWN_SECTION_ROLES = {"intro", "outro", "chorus", "hook", "verse", "bridge",
                       "pre-chorus", "prechorus", "final chorus"}
NUMBER_EQUIVALENTS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
    "10": "ten", "19": "nineteen", "2016": "twenty sixteen",
}


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
    event_type: str = "lead"
    primary_lane: str = "lead"
    structurally_inferred: bool = False
    acoustic_match_texts: list[str] = field(default_factory=list)
    acoustic_match_tokens: list[list[str]] = field(default_factory=list)
    annotation_metadata: list[str] = field(default_factory=list)
    raw_source_line: int | None = None
    raw_source_span: str | None = None


@dataclass
class LyricSection:
    section_id: str
    label: str
    source_start_line: int
    lines: list[LyricLine] = field(default_factory=list)
    raw_label: str = ""
    normalized_label: str = ""
    structural_role: str = "section"
    structural_inferred: bool = False
    fingerprint: str = ""
    repeat_group: str | None = None
    occurrence_index: int = 1
    occurrence_count: int = 1


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
                {"section_id": s.section_id, "label": s.label, "raw_label": s.raw_label,
                 "normalized_label": s.normalized_label, "structural_role": s.structural_role,
                 "structural_inferred": s.structural_inferred, "fingerprint": s.fingerprint,
                 "repeat_group": s.repeat_group, "occurrence_index": s.occurrence_index,
                 "occurrence_count": s.occurrence_count, "source_start_line": s.source_start_line,
                 "lines": [asdict(line) for line in s.lines]}
                for s in self.sections
            ],
        }


def _split_parentheticals(text: str) -> tuple[str, list[str]]:
    adlibs = re.findall(r"\(([^()]*)\)", text)
    lead = re.sub(r"\s*\([^()]*\)", "", text).strip()
    return lead, [a.strip() for a in adlibs if a.strip()]


def section_heading(raw_line: str) -> tuple[str, bool] | None:
    """Return a conservative structural label without changing source text."""
    match = SECTION_RE.match(raw_line) or MALFORMED_SECTION_RE.match(raw_line)
    if not match:
        return None
    label = match.group(1).strip()
    normalized = re.sub(r"\s+", " ", label.lower())
    inferred = bool(MALFORMED_SECTION_RE.match(raw_line))
    if inferred and normalized not in KNOWN_SECTION_ROLES:
        return None
    return label, inferred


def section_role(label: str) -> str:
    normalized = re.sub(r"\s+", " ", label.lower()).strip()
    if normalized in {"prechorus", "pre-chorus"}:
        return "pre_chorus"
    if normalized in {"final chorus", "final hook"}:
        return "chorus"
    return normalized.replace(" ", "_") or "section"


def _event_type(lead: str, adlibs: list[str]) -> tuple[str, str]:
    if lead:
        return ("lead_with_adlib", "lead") if adlibs else ("lead", "lead")
    return "vocal_adlib", "secondary"


def _adlib_views(adlibs: list[str]) -> tuple[list[str], list[list[str]], list[str]]:
    """Return acoustic matching views without changing display annotations.

    Lyric annotations can contain a vocal token followed by a production note,
    e.g. ``Ding! bell sound``.  The display remains authoritative, while the
    acoustic view contains only the vocal material supported by the annotation.
    """
    match_texts: list[str] = []
    match_tokens: list[list[str]] = []
    metadata: list[str] = []
    for adlib in adlibs:
        words = tokens(adlib)
        note: list[str] = []
        if words and words[0] == "ding" and "bell" in words and "sound" in words:
            words = ["ding"]
            note = ["bell sound"]
        match_texts.append(" ".join(words))
        match_tokens.append(words)
        metadata.append("; ".join(note))
    return match_texts, match_tokens, metadata


def _fingerprint(section: LyricSection) -> str:
    return " ".join(line.normalized_text for line in section.lines if line.normalized_text).strip()


def parse_lyrics(path: Path, song_id: str) -> ParsedLyrics:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    digest = hashlib.sha256((text.rstrip("\n") + "\n").encode("utf-8")).hexdigest()
    sections: list[LyricSection] = []
    current: LyricSection | None = None
    section_index = 0
    for number, raw_line in enumerate(text.splitlines(), 1):
        marker = section_heading(raw_line)
        if marker:
            section_index += 1
            label, inferred = marker
            current = LyricSection(f"section_{section_index:03d}", label, number,
                                   raw_label=raw_line, normalized_label=label.lower(),
                                   structural_role=section_role(label),
                                   structural_inferred=inferred)
            sections.append(current)
            continue
        if not raw_line.strip():
            continue
        if current is None:
            section_index += 1
            current = LyricSection(f"section_{section_index:03d}", "Unsectioned", number)
            sections.append(current)
        lead, adlibs = _split_parentheticals(raw_line)
        event_type, lane = _event_type(lead, adlibs)
        match_texts, match_tokens, metadata = _adlib_views(adlibs)
        current.lines.append(LyricLine(
            line_id=f"{current.section_id}_line_{len(current.lines)+1:03d}",
            section_id=current.section_id, source_line=number, original_text=raw_line,
            lead_text=lead, adlibs=adlibs, normalized_text=normalize(lead), tokens=tokens(lead),
            event_type=event_type, primary_lane=lane,
            acoustic_match_texts=match_texts, acoustic_match_tokens=match_tokens,
            annotation_metadata=metadata,
        ))
    groups: dict[str, list[LyricSection]] = {}
    for section in sections:
        section.fingerprint = _fingerprint(section)
        if section.fingerprint:
            groups.setdefault(section.fingerprint, []).append(section)
    for group_index, occurrences in enumerate(groups.values(), 1):
        if len(occurrences) < 2:
            continue
        repeat_group = f"repeat_group_{group_index:03d}"
        for occurrence_index, section in enumerate(occurrences, 1):
            section.repeat_group = repeat_group
            section.occurrence_index = occurrence_index
            section.occurrence_count = len(occurrences)
    return ParsedLyrics(song_id, str(path), digest, sections)
