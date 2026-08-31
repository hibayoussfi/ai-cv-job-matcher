from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Tuple
from urllib.parse import quote

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests


def output_size(fmt: str) -> Tuple[int, int]:
    if fmt == "9:16":
        return (720, 1280)
    if fmt == "1:1":
        return (960, 960)
    return (1280, 720)


def _font(size: int):
    for name in ["DejaVuSans.ttf", "Arial.ttf"]:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int):
    words = text.split()
    lines, line = [], ""
    for word in words:
        candidate = (line + " " + word).strip()
        box = draw.textbbox((0, 0), candidate, font=font)
        if box[2] - box[0] <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def make_storyboard_fallback(prompt: str, path: Path, size: Tuple[int, int], scene_index: int):
    """Zero-key fallback: creates a polished storyboard card, not an AI illustration."""
    w, h = size
    seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)

    y = np.linspace(0, 1, h)[:, None]
    x = np.linspace(0, 1, w)[None, :]
    a = rng.integers(45, 105, size=3)
    b = rng.integers(145, 225, size=3)
    grad = (a[None, None, :] * (1 - y[:, :, None]) + b[None, None, :] * y[:, :, None])
    vignette = 1 - 0.25 * ((x - 0.5) ** 2 + (y - 0.5) ** 2)
    arr = np.clip(grad * vignette[:, :, None], 0, 255).astype(np.uint8)
    img = Image.fromarray(arr).filter(ImageFilter.GaussianBlur(radius=0.5))
    draw = ImageDraw.Draw(img, "RGBA")

    # Abstract foreground/midground/background shapes create useful depth for the animator.
    draw.ellipse((int(w*0.05), int(h*0.58), int(w*0.52), int(h*1.03)), fill=(255,255,255,45))
    draw.ellipse((int(w*0.48), int(h*0.48), int(w*1.06), int(h*1.02)), fill=(15,15,30,55))
    draw.rounded_rectangle((int(w*0.08), int(h*0.08), int(w*0.92), int(h*0.34)), radius=28, fill=(10,10,20,135))

    title_font = _font(max(22, int(w * 0.035)))
    body_font = _font(max(18, int(w * 0.022)))
    draw.text((int(w*0.12), int(h*0.115)), f"SCENE {scene_index}", font=title_font, fill=(255,255,255,245))
    lines = _wrap(draw, prompt, body_font, int(w*0.72))[:7]
    yy = int(h*0.18)
    for line in lines:
        draw.text((int(w*0.12), yy), line, font=body_font, fill=(245,245,250,230))
        yy += int(body_font.size * 1.35) if hasattr(body_font, "size") else 28

    img.save(path, quality=92)
    return path


def generate_pollinations(prompt: str, path: Path, size: Tuple[int, int], api_key: str, model: str = "flux"):
    if not api_key:
        raise ValueError("Pollinations API key is required for AI image generation.")
    w, h = size
    url = f"https://gen.pollinations.ai/image/{quote(prompt)}"
    response = requests.get(
        url,
        params={"model": model, "width": w, "height": h},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=180,
    )
    response.raise_for_status()
    img = Image.open(io.BytesIO(response.content)).convert("RGB")
    img.save(path, quality=94)
    return path


def create_scene_image(prompt: str, path: Path, size: Tuple[int, int], scene_index: int, provider: str, api_key: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    if provider == "Pollinations AI":
        return generate_pollinations(prompt, path, size, api_key)
    return make_storyboard_fallback(prompt, path, size, scene_index)
