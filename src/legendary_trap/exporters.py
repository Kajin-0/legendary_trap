"""Plain ASS, SRT, and WebVTT renderers from canonical timing JSON."""
from __future__ import annotations

import html
from pathlib import Path


def _ts(seconds: float, ass: bool = False) -> str:
    seconds = max(0.0, seconds)
    h, rest = divmod(seconds, 3600); m, rest = divmod(rest, 60); s = int(rest); ms = round((rest-s)*1000)
    if ass: return f"{int(h)}:{int(m):02d}:{s:02d}.{ms//10:02d}"
    return f"{int(h):02d}:{int(m):02d}:{s:02d},{ms:03d}"


def _lines(doc):
    return [line for section in doc["sections"] for line in section["lines"]]


def write_srt(doc: dict, path: Path) -> None:
    text = "\n\n".join(f"{i}\n{_ts(x['start'])} --> {_ts(x['end'])}\n{x['original_text']}" for i, x in enumerate(_lines(doc), 1)) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")


def write_vtt(doc: dict, path: Path) -> None:
    text = "WEBVTT\n\n" + "\n\n".join(f"{i}\n{_ts(x['start']).replace(',', '.')} --> {_ts(x['end']).replace(',', '.')}\n{html.escape(x['original_text'])}" for i, x in enumerate(_lines(doc), 1)) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")


def write_ass(doc: dict, path: Path, karaoke: bool = False) -> None:
    header = "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,1,2,0,2,40,40,50,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    rows = []
    for x in _lines(doc):
        display = x["original_text"]
        if karaoke and x["words"]:
            display = "".join(f"{{\\k{max(1, round((w['end']-w['start'])*100))}}}{w['text']} " for w in x["words"]).strip()
        rows.append(f"Dialogue: 0,{_ts(x['start'], True)},{_ts(x['end'], True)},Default,,0,0,0,,{display}")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
