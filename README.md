# 🎬 Story2Toon

A lightweight **story → 2.5D cartoon video** MVP built for normal laptops.

It converts a written story into scenes, creates/loads scene artwork, applies depth-inspired parallax motion, generates narration with Edge TTS, overlays subtitles, and exports an MP4.

## What v0.1 does

- Deterministic story → scene planning (no paid LLM required)
- Character continuity prompt injected into every scene
- Two image modes:
  - **Zero-key fallback**: creates storyboard frames locally
  - **Pollinations AI**: optional AI image generation with your own API key
- Lightweight pseudo-depth parallax by default
- Optional real depth estimation with Depth Anything V2 Small
- Edge TTS narration (English, German, Arabic, French presets)
- Burned-in captions
- 9:16, 16:9 and 1:1 video formats
- MP4 composition using ImageIO/FFmpeg
- Gradio web UI

## Why this architecture

The project deliberately does **not** try to reproduce Runway/Kling text-to-video diffusion. That would make the app dependent on expensive GPU inference. Story2Toon instead turns still scene art into animated 2.5D shots, which keeps the core pipeline inexpensive and laptop-friendly.

## Requirements

- Python 3.10+
- Internet connection for Edge TTS
- Internet + Pollinations API key only if you select Pollinations AI images

You do not need to install FFmpeg separately; `imageio-ffmpeg` provides a compatible binary for the composition pipeline.

## Quick start

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open the local Gradio URL shown in your terminal.

## AI image mode

Pollinations currently requires authentication for generation. Create a key with Pollinations and paste it into the password field in the UI. The key is used only for the current request and is not written to the repository.

If you do not provide a key, choose **Zero-key fallback**. This keeps the entire visual pipeline local but produces storyboard-style frames rather than fully AI-generated cartoons.

## Optional: real monocular depth

The default animator uses a fast pseudo-depth map so it works without PyTorch.

For stronger depth segmentation:

```bash
pip install -r requirements-depth.txt
```

Then set:

Windows PowerShell:

```powershell
$env:STORY2TOON_REAL_DEPTH="1"
python app.py
```

macOS/Linux:

```bash
STORY2TOON_REAL_DEPTH=1 python app.py
```

The first run downloads `depth-anything/Depth-Anything-V2-Small-hf` and may be much slower on CPU.

## Project structure

```text
story2toon/
├── app.py
├── requirements.txt
├── requirements-depth.txt
├── story2toon/
│   ├── story.py       # story → scene plan
│   ├── images.py      # local/Pollinations image providers
│   ├── depth.py       # pseudo/Depth Anything depth maps
│   ├── animate.py     # 2.5D parallax + captions
│   ├── tts.py         # Edge TTS
│   ├── composer.py    # audio mux + final concat
│   └── pipeline.py    # orchestration
├── tests/
└── .github/workflows/tests.yml
```

## Important limitation

v0.1 is a **2.5D animator**, not full character animation. It does not yet make a character truly walk, lip-sync, change pose, or preserve identity using a reference-image adapter. Those are v0.2/v0.3 problems and require a different inference layer.

## Suggested next milestones

1. Add editable scene cards before final rendering.
2. Add reference-image character consistency (IP-Adapter/InstantID style workflow).
3. Add foreground segmentation and background inpainting for stronger parallax.
4. Add music/SFX tracks and volume ducking.
5. Add dialogue with multiple voices.
6. Add optional image-to-video provider adapters without coupling the core app to one paid vendor.

## License

MIT
