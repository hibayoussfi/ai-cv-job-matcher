from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from .animate import render_scene
from .composer import concatenate, mux_audio
from .images import create_scene_image, output_size
from .story import plan_scenes, scenes_as_dicts
from .tts import synthesize


def build_video(
    story: str,
    character: str,
    style: str,
    voice: str,
    fmt: str,
    target_duration: float,
    scene_count: int,
    image_provider: str,
    pollinations_key: str,
    fps: int = 20,
):
    scenes = plan_scenes(story, character, style, scene_count, target_duration)
    size = output_size(fmt)

    work = Path(tempfile.mkdtemp(prefix="story2toon_"))
    gallery = []
    final_scenes = []

    for scene in scenes:
        image_path = work / f"scene_{scene.index:02d}.jpg"
        audio_path = work / f"scene_{scene.index:02d}.mp3"
        srt_path = work / f"scene_{scene.index:02d}.srt"
        silent_video = work / f"scene_{scene.index:02d}_silent.mp4"
        scene_video = work / f"scene_{scene.index:02d}.mp4"

        create_scene_image(
            scene.visual_prompt,
            image_path,
            size,
            scene.index,
            image_provider,
            pollinations_key,
        )
        gallery.append(str(image_path))

        synthesize(scene.narration, voice, audio_path, srt_path)
        render_scene(
            image_path=image_path,
            output_path=silent_video,
            duration=scene.duration,
            fps=fps,
            size=size,
            camera=scene.camera,
            caption=scene.narration,
        )
        mux_audio(silent_video, audio_path, scene_video, scene.duration)
        final_scenes.append(scene_video)

    output = work / "story2toon_final.mp4"
    concatenate(final_scenes, output)
    scene_json = json.dumps(scenes_as_dicts(scenes), ensure_ascii=False, indent=2)
    return str(output), gallery, scene_json, work


def export_copy(video_path: str, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video_path, destination)
    return destination
