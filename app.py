from __future__ import annotations

import traceback
import gradio as gr

from story2toon.pipeline import build_video
from story2toon.tts import VOICE_MAP


def generate(story, character, style, voice, fmt, duration, scene_count, provider, api_key):
    try:
        video, gallery, scenes_json, _ = build_video(
            story=story,
            character=character,
            style=style,
            voice=voice,
            fmt=fmt,
            target_duration=float(duration),
            scene_count=int(scene_count),
            image_provider=provider,
            pollinations_key=api_key or "",
        )
        mode_note = (
            "AI images via Pollinations." if provider == "Pollinations AI"
            else "Zero-key storyboard fallback images. Add a Pollinations key for AI illustrations."
        )
        return video, gallery, scenes_json, f"Done. {mode_note}"
    except Exception as exc:
        return None, [], "", f"Generation failed: {exc}\n\n{traceback.format_exc(limit=2)}"


CSS = """
.gradio-container {max-width: 1180px !important;}
.hero {text-align:center; padding: 10px 0 18px 0;}
.hero h1 {font-size: 2.4rem; margin-bottom: .25rem;}
.hero p {opacity:.75;}
"""

with gr.Blocks(title="Story2Toon", css=CSS) as demo:
    gr.HTML("""
    <div class='hero'>
      <h1>🎬 Story2Toon</h1>
      <p>Story → cartoon scenes → 2.5D motion → voice → subtitles → MP4</p>
    </div>
    """)

    with gr.Row():
        with gr.Column(scale=5):
            story = gr.Textbox(
                label="Your story",
                lines=10,
                placeholder="Luna arrives in Japan. She walks through a quiet street...",
            )
            character = gr.Textbox(
                label="Character continuity description",
                lines=3,
                value="Luna, young adult cartoon traveler, dark wavy hair, yellow jacket, blue jeans, white sneakers",
            )
            style = gr.Dropdown(
                ["Stylized 3D cartoon", "2D storybook illustration", "Anime-inspired cartoon", "Clay-like cartoon"],
                value="Stylized 3D cartoon",
                label="Visual style",
            )
        with gr.Column(scale=3):
            voice = gr.Dropdown(list(VOICE_MAP), value="English Female", label="Narration voice")
            fmt = gr.Radio(["9:16", "16:9", "1:1"], value="9:16", label="Video format")
            duration = gr.Slider(15, 90, value=30, step=5, label="Target duration (approx. seconds)")
            scene_count = gr.Slider(3, 8, value=5, step=1, label="Scenes")
            provider = gr.Radio(["Zero-key fallback", "Pollinations AI"], value="Zero-key fallback", label="Image provider")
            api_key = gr.Textbox(label="Pollinations API key (optional)", type="password", placeholder="Only needed for Pollinations AI")
            generate_btn = gr.Button("✨ Create Story Video", variant="primary")

    status = gr.Textbox(label="Status", interactive=False)
    with gr.Row():
        video = gr.Video(label="Final video")
        scenes_json = gr.Code(label="Scene plan", language="json")
    gallery = gr.Gallery(label="Generated storyboard", columns=5, height="auto")

    generate_btn.click(
        generate,
        inputs=[story, character, style, voice, fmt, duration, scene_count, provider, api_key],
        outputs=[video, gallery, scenes_json, status],
    )

if __name__ == "__main__":
    demo.launch()
