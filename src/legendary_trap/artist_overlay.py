"""Independent final-resolution RGBA artist identity overlay."""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .artist_lockup import ArtistLockup

FINAL_WIDTH, FINAL_HEIGHT = 1920, 1080
PFP_SIZE = 128
PFP_SUPERSAMPLE = 4
LEFT = 56
TOP = 56


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    result = subprocess.run(["fc-match", "-f", "%{file}", name], check=True,
                            capture_output=True, text=True, timeout=10)
    return ImageFont.truetype(result.stdout.strip(), size)


def _cover_crop(path: Path, size: int) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    scale = max(size / image.width, size / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - size) // 2
    top = (resized.height - size) // 2
    return resized.crop((left, top, left + size, top + size))


def _masked_pfp(path: Path, shape: str) -> Image.Image:
    size = PFP_SIZE * PFP_SUPERSAMPLE
    image = _cover_crop(path, size)
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    if shape == "circle":
        draw.ellipse((0, 0, size - 1, size - 1), fill=255)
    else:
        draw.rounded_rectangle((0, 0, size - 1, size - 1),
                               radius=16 * PFP_SUPERSAMPLE, fill=255)
    image.putalpha(mask)
    return image.resize((PFP_SIZE, PFP_SIZE), Image.Resampling.LANCZOS)


def _draw_edge(draw: ImageDraw.ImageDraw, x: int, y: int, shape: str) -> None:
    box = (x + 1, y + 1, x + PFP_SIZE - 2, y + PFP_SIZE - 2)
    edge = (255, 235, 213, 205)
    if shape == "circle":
        draw.ellipse(box, outline=edge, width=2)
    else:
        draw.rounded_rectangle(box, radius=15, outline=edge, width=2)


def build_artist_overlay(lockup: ArtistLockup, title: str) -> Image.Image:
    """Build a deterministic 1920x1080 transparent identity layer."""
    overlay = Image.new("RGBA", (FINAL_WIDTH, FINAL_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    pfp_count = len(lockup.pfp_paths)
    text_x = LEFT + (pfp_count * (PFP_SIZE + 10) + 22 if pfp_count else 0)
    if lockup.name:
        artist_font = _font("Super Crown", 36)
        title_font = _font("Barlow Condensed", 22)
        if pfp_count:
            for index, path in enumerate(lockup.pfp_paths):
                shape = lockup.crop_shapes[index] if index < len(lockup.crop_shapes) else "circle"
                image = _masked_pfp(path, shape)
                x = LEFT + index * (PFP_SIZE + 10)
                overlay.alpha_composite(image, (x, TOP))
                _draw_edge(ImageDraw.Draw(overlay), x, TOP, shape)
        draw = ImageDraw.Draw(overlay)
        draw.text((text_x, TOP + 15), lockup.name, font=artist_font,
                  fill=(255, 249, 240, 255), stroke_width=2, stroke_fill=(20, 26, 38, 210))
        draw.text((text_x, TOP + 61), title, font=title_font,
                  fill=(233, 216, 200, 235), stroke_width=1, stroke_fill=(20, 26, 38, 170))
    return overlay
