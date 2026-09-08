"""Chronology-constrained authoritative-token alignment and local refinement."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import pairwise

from .lyrics import NUMBER_EQUIVALENTS, LyricLine, ParsedLyrics, normalize


@dataclass
class AcousticToken:
    text: str
    start: float
    end: float
    probability: float


def asr_tokens(asr: dict) -> list[AcousticToken]:
    return [AcousticToken(w["text"], w["start"], w["end"], w.get("probability", 0.0))
            for s in asr["segments"] for w in s["words"]]


def fuse_local_asr(base_asr: dict, local_asr: dict) -> dict:
    """Replace full-song evidence only inside declared windows."""
    windows = [(x["window"]["start"], x["window"]["end"]) for x in local_asr["windows"]]
    base_words = [w for s in base_asr["segments"] for w in s["words"]]
    words = [w for w in base_words if not any(w["start"] < end and w["end"] > start for start, end in windows)]
    for row in local_asr["windows"]:
        for segment in row["segments"]:
            words.extend(segment["words"])
    words.sort(key=lambda w: (w["start"], w["end"]))
    return {**base_asr, "segments": [{"start": words[0]["start"], "end": words[-1]["end"],
                                      "text": " ".join(w["text"] for w in words), "words": words}] if words else []}


def _sim(a: str, b: str) -> float:
    a, b = normalize(a), normalize(b)
    if a == b: return 1.0
    if NUMBER_EQUIVALENTS.get(a) == b or NUMBER_EQUIVALENTS.get(b) == a: return 0.95
    if a.replace("'", "") == b.replace("'", ""): return 0.92
    ratio = SequenceMatcher(None, a, b).ratio()
    # Small ASR spelling/slang variants are useful as acoustic evidence, but
    # they never replace the authoritative token in the output.
    aliases = {"cuz": "because", "cause": "because", "gonna": "going to", "wanna": "want to"}
    if aliases.get(a) == b or aliases.get(b) == a:
        return 0.88
    return ratio


def align_tokens(auth: list[str], acoustic: list[AcousticToken]) -> tuple[dict[int, AcousticToken], float, int]:
    """Global monotonic DP. Skips are explicit and never alter authoritative text."""
    n, m = len(auth), len(acoustic)
    neg = -1e9
    dp = [[neg] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple[int, int, str] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            val = dp[i][j]
            if val <= neg / 2: continue
            if i < n and val - 0.28 > dp[i + 1][j]:
                dp[i + 1][j], back[i + 1][j] = val - 0.28, (i, j, "skip_auth")
            if j < m and val - 0.12 > dp[i][j + 1]:
                dp[i][j + 1], back[i][j + 1] = val - 0.12, (i, j, "skip_asr")
            if i < n and j < m:
                score = val + 1.25 * _sim(auth[i], acoustic[j].text) - 0.35
                if score > dp[i + 1][j + 1]:
                    dp[i + 1][j + 1], back[i + 1][j + 1] = score, (i, j, "match")
    i, j, matches = n, m, {}
    while i or j:
        prev = back[i][j]
        if prev is None: break
        pi, pj, op = prev
        if op == "match" and _sim(auth[pi], acoustic[pj].text) >= 0.42:
            # Replace disposable ASR wording with the authoritative token while
            # retaining only its acoustic coordinates and confidence.
            matches[pi] = AcousticToken(auth[pi], acoustic[pj].start, acoustic[pj].end, acoustic[pj].probability)
        i, j = pi, pj
    coverage = len(matches) / n if n else 1.0
    return matches, coverage, n - len(matches)


def _line_word_ranges(parsed: ParsedLyrics) -> list[tuple[LyricLine, int, int]]:
    out, index = [], 0
    for line in parsed.lines:
        out.append((line, index, index + len(line.tokens)))
        index += len(line.tokens)
    return out


def build_alignment(parsed: ParsedLyrics, asr: dict, duration: float) -> tuple[list[dict], dict]:
    acoustic = asr_tokens(asr)
    auth = [t for line in parsed.lines for t in line.tokens]
    matches, coverage, unresolved = align_tokens(auth, acoustic)
    rows = []
    for line, lo, hi in _line_word_ranges(parsed):
        found = [matches[i] for i in range(lo, hi) if i in matches]
        similarities = [_sim(line.tokens[i - lo], matches[i].text) for i in range(lo, hi) if i in matches]
        if found:
            start, end = min(w.start for w in found), max(w.end for w in found)
            token_coverage = len(found) / len(line.tokens) if line.tokens else 1.0
            lexical_match = sum(similarities) / len(similarities)
            acoustic_support = sum(w.probability for w in found) / len(found)
            gaps = [b.start - a.end for a, b in pairwise(found)]
            temporal_consistency = 1.0 if not gaps else max(0.0, min(1.0, 1.0 - sum(max(0.0, g - 2.0) for g in gaps) / (2.0 * len(gaps))))
            conf = (0.35 * token_coverage + 0.25 * lexical_match +
                    0.20 * temporal_consistency + 0.20 * acoustic_support)
            components = {"token_coverage": token_coverage, "lexical_match": lexical_match,
                          "temporal_consistency": temporal_consistency, "acoustic_support": acoustic_support}
        else:
            start = end = None
            conf = 0.0
            components = {"token_coverage": 0.0, "lexical_match": 0.0,
                          "temporal_consistency": 0.0, "acoustic_support": 0.0}
        rows.append({"line": line, "start": start, "end": end, "confidence": min(1.0, max(0.0, conf)),
                     "confidence_components": components, "words": found,
                     "word_evidence": [{"token_index": i - lo, "text": matches[i].text,
                                        "start": matches[i].start, "end": matches[i].end,
                                        "probability": matches[i].probability, "timing_source": "asr"}
                                       for i in range(lo, hi) if i in matches],
                     "matched_tokens": len(found), "total_tokens": len(line.tokens)})
    # Fill missing lines only inside the bounded neighboring evidence window.
    for idx, row in enumerate(rows):
        if row["start"] is not None: continue
        prev = next((e for e in reversed(rows[:idx]) if e["end"] is not None), None)
        nxt = next((e for e in rows[idx + 1:] if e["start"] is not None), None)
        left = prev["end"] if prev else 0.0
        right = nxt["start"] if nxt else duration
        count = sum(1 for r in rows[idx:] if r["start"] is None and (nxt is None or r is not nxt))
        # Conservative interpolation is explicitly low confidence, not fabricated precision.
        row["start"], row["end"] = left, max(left, min(right, left + max(0.25, (right-left) / max(1, count))))
        row["confidence"] = 0.12
        row["confidence_components"] = {"token_coverage": 0.0, "lexical_match": 0.0,
                                        "temporal_consistency": 0.0, "acoustic_support": 0.0}
    # Section bounds preserve chronological repeated-section identity.
    sections = []
    offset = 0
    for section in parsed.sections:
        section_rows = rows[offset:offset + len(section.lines)]
        offset += len(section.lines)
        start = min(r["start"] for r in section_rows) if section_rows else 0.0
        end = max(r["end"] for r in section_rows) if section_rows else start
        sections.append({"section": section, "rows": section_rows, "start": start, "end": end})
    diagnostics = {"asr_token_count": len(acoustic), "authoritative_token_count": len(auth),
                   "token_alignment_coverage": coverage, "unresolved_authoritative_tokens": unresolved,
                   "line_alignment_coverage": sum(r["matched_tokens"] > 0 for r in rows) / len(rows) if rows else 1.0}
    return sections, diagnostics
