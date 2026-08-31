from __future__ import annotations

import os
from functools import lru_cache
import numpy as np
from PIL import Image, ImageFilter


@lru_cache(maxsize=1)
def _depth_pipeline():
    from transformers import pipeline
    return pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf")


def pseudo_depth(image: Image.Image) -> np.ndarray:
    """Fast no-model depth proxy used by default for lightweight parallax."""
    gray = np.asarray(image.convert("L").filter(ImageFilter.GaussianBlur(18)), dtype=np.float32) / 255.0
    h, w = gray.shape
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w * 0.5, h * 0.58
    radial = 1.0 - np.sqrt(((xx-cx)/(w*0.8))**2 + ((yy-cy)/(h*0.8))**2)
    radial = np.clip(radial, 0, 1)
    # Bright/central content receives slightly more foreground weight.
    depth = 0.52 * gray + 0.48 * radial
    lo, hi = float(depth.min()), float(depth.max())
    return (depth - lo) / max(1e-6, hi - lo)


def estimate_depth(image: Image.Image) -> np.ndarray:
    if os.getenv("STORY2TOON_REAL_DEPTH", "0") == "1":
        result = _depth_pipeline()(image)
        depth = result["depth"].resize(image.size)
        arr = np.asarray(depth, dtype=np.float32)
        arr -= arr.min()
        arr /= max(1e-6, arr.max())
        return arr
    return pseudo_depth(image)
