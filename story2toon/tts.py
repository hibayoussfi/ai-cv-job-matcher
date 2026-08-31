from __future__ import annotations

import asyncio
from pathlib import Path
import edge_tts


VOICE_MAP = {
    "English Female": "en-US-AriaNeural",
    "English Male": "en-US-GuyNeural",
    "German Female": "de-DE-KatjaNeural",
    "German Male": "de-DE-ConradNeural",
    "Arabic Female": "ar-SA-ZariyahNeural",
    "Arabic Male": "ar-SA-HamedNeural",
    "French Female": "fr-FR-DeniseNeural",
}


async def _save(text: str, voice: str, media_path: Path, srt_path: Path):
    communicate = edge_tts.Communicate(text, voice=voice)
    submaker = edge_tts.SubMaker()
    with media_path.open("wb") as audio:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                submaker.feed(chunk)
    srt_path.write_text(submaker.get_srt(), encoding="utf-8")


def synthesize(text: str, voice_label: str, media_path: Path, srt_path: Path):
    voice = VOICE_MAP.get(voice_label, VOICE_MAP["English Female"])
    media_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_save(text, voice, media_path, srt_path))
    return media_path, srt_path
