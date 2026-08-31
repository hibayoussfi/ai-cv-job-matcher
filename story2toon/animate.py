from __future__ import annotations

from pathlib import Path
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio.v2 as imageio

from .depth import estimate_depth


def _font(size: int):
    for name in ["DejaVuSans.ttf", "Arial.ttf"]:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _cover(image: Image.Image, size):
    w, h = size
    scale = max(w / image.width, h / image.height)
    resized = image.resize((math.ceil(image.width * scale), math.ceil(image.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


def _shift(arr: np.ndarray, dx: int, dy: int):
    return np.roll(np.roll(arr, dy, axis=0), dx, axis=1)


def _caption(frame: Image.Image, text: str):
    if not text:
        return frame
    draw = ImageDraw.Draw(frame, "RGBA")
    w, h = frame.size
    font = _font(max(24, int(w * 0.028)))
    max_width = int(w * 0.82)
    words, lines, line = text.split(), [], ""
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
    lines = lines[-3:]
    line_h = int(getattr(font, "size", 28) * 1.25)
    box_h = line_h * len(lines) + 34
    y0 = h - box_h - int(h * 0.055)
    draw.rounded_rectangle((int(w*0.07), y0, int(w*0.93), y0 + box_h), radius=22, fill=(0,0,0,150))
    y = y0 + 16
    for line in lines:
        bbox = draw.textbbox((0,0), line, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((w-tw)//2, y), line, font=font, fill=(255,255,255,245))
        y += line_h
    return frame


def _motion_offsets(camera: str, p: float, strength: float):
    x = (p - 0.5) * 2
    if camera in {"parallax_left", "pan_left"}:
        return -x * strength, 0.0, 1.02
    if camera in {"parallax_right", "pan_right"}:
        return x * strength, 0.0, 1.02
    if camera == "slow_pull_back":
        return 0.0, 0.0, 1.08 - 0.06 * p
    return 0.0, 0.0, 1.02 + 0.06 * p


def render_scene(image_path: Path, output_path: Path, duration: float, fps: int, size, camera: str, caption: str):
    source = _cover(Image.open(image_path).convert("RGB"), size)
    base = np.asarray(source)
    depth = estimate_depth(source)
    near = np.clip((depth - 0.58) / 0.28, 0, 1)[..., None]
    mid = np.clip(1 - np.abs(depth - 0.5) / 0.24, 0, 1)[..., None] * 0.55

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(output_path, fps=fps, codec="libx264", quality=7, macro_block_size=None)
    frames = max(1, int(duration * fps))
    try:
        for i in range(frames):
            p = i / max(1, frames - 1)
            offset, _, zoom = _motion_offsets(camera, p, strength=max(8, size[0] * 0.035))
            far_arr = _shift(base, int(offset * 0.18), 0)
            mid_arr = _shift(base, int(offset * 0.55), 0)
            near_arr = _shift(base, int(offset), 0)
            comp = far_arr.astype(np.float32)
            comp = comp * (1-mid) + mid_arr.astype(np.float32) * mid
            comp = comp * (1-near) + near_arr.astype(np.float32) * near
            frame = Image.fromarray(np.clip(comp, 0, 255).astype(np.uint8))

            if abs(zoom - 1.0) > 1e-3:
                zw, zh = int(frame.width * zoom), int(frame.height * zoom)
                z = frame.resize((zw, zh), Image.Resampling.LANCZOS)
                left = (zw-frame.width)//2
                top = (zh-frame.height)//2
                frame = z.crop((left, top, left+frame.width, top+frame.height))
            frame = _caption(frame, caption)
            writer.append_data(np.asarray(frame))
    finally:
        writer.close()
    return output_path
