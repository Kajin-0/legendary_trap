"""Readable visualizer subtitle styling, separate from research renderers."""
from __future__ import annotations

from pathlib import Path

from .exporters import _lines, _ts, write_srt, write_vtt


def _ass_text(value: str) -> str:
    return value.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def write_visual_ass(document: dict, path: Path, title: str = "FOCUS",
                     width: int = 1920, height: int = 1080) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyric,DejaVu Sans,56,&H00F5FBFF,&H00F5FBFF,&H00131E2E,&H96070B12,1,0,1,3,1,2,110,110,150,1
Style: Title,DejaVu Sans,28,&H009AB9CC,&H009AB9CC,&H00131E2E,&H00000000,1,0,1,2,0,8,90,90,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = [f"Dialogue: 0,0:00:00.00,0:00:08.00,Title,,0,0,0,,{_ass_text(title.upper())}"]
    for line in _lines(document):
        if line["end"] <= line["start"]:
            continue
        rows.append(f"Dialogue: 1,{_ts(line['start'], True)},{_ts(line['end'], True)},Lyric,,0,0,0,,{{\\fad(160,220)}}{_ass_text(line['original_text'])}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")


def write_subtitles(document: dict, output_dir: Path, title: str,
                    width: int = 1920, height: int = 1080) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ass = output_dir / f"{title.lower()}.ass"
    srt = output_dir / f"{title.lower()}.srt"
    vtt = output_dir / f"{title.lower()}.vtt"
    write_visual_ass(document, ass, title, width, height)
    write_srt(document, srt)
    write_vtt(document, vtt)
    return {"ass": str(ass), "srt": str(srt), "vtt": str(vtt)}
