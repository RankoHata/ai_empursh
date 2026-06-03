"""
Text-to-speech using edge-tts (Microsoft free TTS service).
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

VOICE = "zh-CN-XiaoxiaoNeural"
TEMP_DIR = Path(__file__).parent.parent / "temp"


async def synthesize(text: str, output_path: str | None = None) -> str:
    """Convert text to speech and save as MP3. Returns the file path."""
    import edge_tts

    if output_path is None:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        output_path = str(TEMP_DIR / f"tts_{os.urandom(6).hex()}.mp3")

    communicate = edge_tts.Communicate(text=text, voice=VOICE)
    await communicate.save(output_path)
    logger.info("TTS saved to %s (%d chars)", output_path, len(text))
    return output_path


def synthesize_sync(text: str, output_path: str | None = None) -> str:
    """Synchronous wrapper for synthesize."""
    return asyncio.run(synthesize(text, output_path))
