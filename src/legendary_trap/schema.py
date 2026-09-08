"""Canonical timing JSON serialization (schema version 1)."""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA_VERSION = "1.0"


def make_document(song_id: str, audio: dict, parsed, sections: list[dict], alignment: dict,
                  diagnostics: dict) -> dict:
    rendered = []
    for block in sections:
        lines = []
        for row in block["rows"]:
            line = row["line"]
            evidence = {x["token_index"]: x for x in row.get("word_evidence", [])}
            words = []
            for token_index, token in enumerate(line.tokens):
                item = evidence.get(token_index)
                if item:
                    words.append({"text": token, "start": round(item["start"], 3),
                                  "end": round(item["end"], 3), "confidence": round(item["probability"], 4),
                                  "timing_source": item["timing_source"], "acoustic_supported": True})
                else:
                    span = max(0.04, (row["end"] - row["start"]) / max(1, len(line.tokens)))
                    start = row["start"] + token_index * span
                    words.append({"text": token, "start": round(start, 3), "end": round(min(row["end"], start + span), 3),
                                  "confidence": 0.0, "timing_source": "interpolated" if evidence else "line_estimate",
                                  "acoustic_supported": False})
            lines.append({"line_id": line.line_id, "source_line": line.source_line,
                          "original_text": line.original_text, "lead_text": line.lead_text,
                          "adlibs": line.adlibs, "start": round(row["start"], 3),
                          "end": round(max(row["start"], row["end"]), 3),
                          "confidence": round(row["confidence"], 4), "matched_tokens": row["matched_tokens"],
                          "confidence_components": {k: round(v, 4) for k, v in row["confidence_components"].items()},
                          "acoustic_start": round(row.get("acoustic_start", row["start"]), 3),
                          "acoustic_end": round(row.get("acoustic_end", row["end"]), 3),
                          "total_tokens": row["total_tokens"], "words": words})
        rendered.append({"section_id": block["section"].section_id, "label": block["section"].label,
                         "start": round(block["start"], 3), "end": round(block["end"], 3),
                         "confidence": round(sum(x["confidence"] for x in block["rows"]) / len(block["rows"],) if block["rows"] else 0, 4),
                         "lines": lines})
    return {"schema_version": SCHEMA_VERSION, "song_id": song_id, "audio": audio,
            "alignment": alignment, "sections": rendered, "diagnostics": diagnostics,
            "authoritative_lyrics": {"path": parsed.path, "sha256": parsed.sha256}}


def write_json(document: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
