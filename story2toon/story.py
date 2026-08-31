from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import List


@dataclass
class Scene:
    index: int
    narration: str
    visual_prompt: str
    camera: str
    duration: float


def _sentences(text: str) -> List[str]:
    clean = re.sub(r"\s+", " ", text.strip())
    if not clean:
        return []
    parts = re.split(r"(?<=[.!?])\s+", clean)
    return [p.strip() for p in parts if p.strip()]


def _chunks(items: List[str], n: int) -> List[str]:
    if not items:
        return []
    n = max(1, min(n, len(items)))
    size = math.ceil(len(items) / n)
    chunks = [" ".join(items[i : i + size]) for i in range(0, len(items), size)]
    while len(chunks) > n:
        chunks[-2] += " " + chunks[-1]
        chunks.pop()
    return chunks


def plan_scenes(
    story: str,
    character: str,
    style: str,
    scene_count: int = 5,
    target_duration: float = 30.0,
) -> List[Scene]:
    """Split a story into deterministic scenes without requiring an LLM."""
    sentences = _sentences(story)
    if not sentences:
        raise ValueError("Please enter a story.")

    chunks = _chunks(sentences, scene_count)
    base = max(3.0, target_duration / max(1, len(chunks)))
    cameras = [
        "slow_push_in",
        "parallax_left",
        "pan_right",
        "slow_pull_back",
        "parallax_right",
        "pan_left",
    ]

    scenes: List[Scene] = []
    for i, narration in enumerate(chunks, start=1):
        # Rough narration allowance: ~2.3 spoken words/s + breathing room.
        words = max(1, len(narration.split()))
        duration = max(base, words / 2.3 + 0.8)
        prompt = (
            f"{style}. Story scene {i}. {narration} "
            f"Main character continuity: {character}. "
            "Cinematic composition, clear foreground/midground/background separation, "
            "expressive but family-friendly cartoon storytelling, no text, no watermark."
        )
        scenes.append(
            Scene(
                index=i,
                narration=narration,
                visual_prompt=prompt,
                camera=cameras[(i - 1) % len(cameras)],
                duration=round(duration, 2),
            )
        )
    return scenes


def scenes_as_dicts(scenes: List[Scene]):
    return [asdict(scene) for scene in scenes]
