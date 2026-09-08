"""Readable visualizer subtitle styling, separate from research renderers."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from .exporters import _lines, _ts, write_srt, write_vtt


def _ass_text(value: str) -> str:
    return value.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def clip_render_document(document: dict, start: float, duration: float) -> dict:
    """Clip only positive-duration lyric events intersecting a preview window."""
    if start < 0 or duration < 0:
        raise ValueError("preview start and duration must be non-negative")
    end = start + duration
    clipped = deepcopy(document)
    for section in clipped.get("sections", []):
        kept = []
        for line in section.get("lines", []):
            line_start, line_end = float(line["start"]), float(line["end"])
            if line_end <= line_start or line_end <= start or line_start >= end:
                continue
            line["start"] = round(max(0.0, line_start - start), 3)
            line["end"] = round(min(duration, line_end - start), 3)
            if line["end"] > line["start"]:
                kept.append(line)
        section["lines"] = kept
    clipped["audio"] = {**clipped.get("audio", {}), "duration_seconds": duration}
    return clipped


def write_visual_ass(document: dict, path: Path, title: str = "FOCUS",
                     width: int = 1920, height: int = 1080,
                     lyric_font: str = "Montserrat", lyric_size: int = 84,
                     lyric_bold: int = 1, include_title: bool = True) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyric,{lyric_font},{lyric_size},&H00FFF9F0,&H00FFF9F0,&H00141A26,&H90070B12,{lyric_bold},0,1,2,1,5,180,180,0,1
Style: Title,Lato Bold,28,&H00F2CFA5,&H00F2CFA5,&H00141A26,&H00000000,1,0,1,2,0,8,90,90,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = []
    if include_title:
        rows.append(f"Dialogue: 0,0:00:00.00,0:00:08.00,Title,,0,0,0,,{_ass_text(title.upper())}")
    for line in _lines(document):
        if line["end"] <= line["start"]:
            continue
        rows.append(f"Dialogue: 1,{_ts(line['start'], True)},{_ts(line['end'], True)},Lyric,,0,0,0,,{{\\an5\\pos(960,540)\\fad(160,220)}}{_ass_text(line['original_text'])}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")


def write_subtitles(document: dict, output_dir: Path, title: str,
                    width: int = 1920, height: int = 1080,
                    lyric_font: str = "Montserrat", lyric_size: int = 84,
                    lyric_bold: int = 1, include_title: bool = True) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ass = output_dir / f"{title.lower()}.ass"
    srt = output_dir / f"{title.lower()}.srt"
    vtt = output_dir / f"{title.lower()}.vtt"
    write_visual_ass(document, ass, title, width, height, lyric_font, lyric_size, lyric_bold,
                     include_title)
    write_srt(document, srt)
    write_vtt(document, vtt)
    return {"ass": str(ass), "srt": str(srt), "vtt": str(vtt)}
