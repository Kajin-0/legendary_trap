"""Compare full-song renderable subtitle rows with repaired timing documents."""
from __future__ import annotations

import json
import re
from pathlib import Path

from legendary_trap.subtitle_render import write_subtitles

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/v3_individual_audit"


def parse_ass(path: Path) -> list[dict]:
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.startswith("Dialogue:") or ",Lyric,," not in raw and ",Adlib,," not in raw:
            continue
        fields = raw.split(",", 9)
        text = fields[9]
        text = re.sub(r"^\{[^}]*\}", "", text)
        rows.append({"style": fields[3], "text": text})
    return rows


def song_parity(song: str) -> dict:
    document = json.loads((ROOT / "output" / song / "timing.json").read_text())
    target = OUT / "parity_ass" / song
    paths = write_subtitles(document, target, song.upper(), lyric_font="Barlow Condensed",
                            lyric_size=90, include_title=False)
    rendered = parse_ass(Path(paths["ass"]))
    expected = [{"style": "Adlib" if (str(line.get("event_type", "")).lower() in
                 {"vocal_adlib", "adlib_only", "interjection"} or
                 str(line.get("original_text", "")).lstrip().startswith("(")) else "Lyric",
                 "text": line["original_text"]}
                for section in document["sections"] for line in section["lines"]
                if float(line["end"]) > float(line["start"])]
    missing = [row for row in expected if row not in rendered]
    extra = [row for row in rendered if row not in expected]
    return {"song": song, "authoritative_renderable_lines": len(expected),
            "rendered_lines": len(rendered), "text_mismatches": 0 if not missing and not extra else len(missing) + len(extra),
            "missing_supported_lines": missing, "unsupported_phantom_lines": extra,
            "exact_text_match": expected == rendered, "ass": str(Path(paths["ass"]).relative_to(ROOT))}


def main() -> None:
    report = {song: song_parity(song) for song in ("focus", "we_got_chemistry")}
    (OUT / "render_parity.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
