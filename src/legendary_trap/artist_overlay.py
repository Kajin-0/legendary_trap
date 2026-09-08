"""Independent final-resolution RGBA artist identity overlay."""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .artist_lockup import ArtistLockup

FINAL_WIDTH, FINAL_HEIGHT = 1920, 1080
PFP_SIZE = 128
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
    image = _cover_crop(path, PFP_SIZE)
    mask = Image.new("L", (PFP_SIZE, PFP_SIZE), 0)
    draw = ImageDraw.Draw(mask)
    if shape == "circle":
        draw.ellipse((0, 0, PFP_SIZE - 1, PFP_SIZE - 1), fill=255)
    else:
        draw.rounded_rectangle((0, 0, PFP_SIZE - 1, PFP_SIZE - 1), radius=16, fill=255)
    image.putalpha(mask)
    return image


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
                image = _masked_pfp(path, lockup.crop_shapes[index] if index < len(lockup.crop_shapes) else "circle")
                x = LEFT + index * (PFP_SIZE + 10)
                shadow = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
                shadow_piece = Image.new("RGBA", image.size, (0, 0, 0, 150))
                shadow_piece.putalpha(image.getchannel("A").filter(ImageFilter.GaussianBlur(5)))
                shadow.alpha_composite(shadow_piece, (x + 3, TOP + 4))
                overlay = Image.alpha_composite(overlay, shadow)
                overlay.alpha_composite(image, (x, TOP))
        draw = ImageDraw.Draw(overlay)
        draw.text((text_x, TOP + 15), lockup.name, font=artist_font,
                  fill=(255, 249, 240, 255), stroke_width=2, stroke_fill=(20, 26, 38, 210))
        draw.text((text_x, TOP + 61), title, font=title_font,
                  fill=(233, 216, 200, 235), stroke_width=1, stroke_fill=(20, 26, 38, 170))
    return overlay
