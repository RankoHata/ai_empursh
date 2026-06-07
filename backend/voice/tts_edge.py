"""
Text-to-speech using Microsoft edge-tts (free cloud service).

Wraps the existing edge-tts logic in a BaseTTSEngine subclass.
"""

import asyncio
import logging
import os
from pathlib import Path

from voice.tts_base import BaseTTSEngine

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"
TEMP_DIR = Path(__file__).parent.parent / "temp"


class EdgeTTSEngine(BaseTTSEngine):
    """Microsoft Edge TTS — cloud-based, excellent Chinese quality, no GPU needed."""

    def __init__(self, voice: str = DEFAULT_VOICE) -> None:
        self._voice = voice
        logger.info("EdgeTTSEngine initialized: voice=%s", voice)

    @property
    def name(self) -> str:
        return "edge-tts"

    @property
    def sample_rate(self) -> int:
        return 24000

    async def synthesize(self, text: str, output_path: str | None = None) -> str:
        """Convert text to speech and save as MP3. Returns the file path."""
        import edge_tts

        if output_path is None:
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            output_path = str(TEMP_DIR / f"tts_{os.urandom(6).hex()}.mp3")

        communicate = edge_tts.Communicate(text=text, voice=self._voice)
        await communicate.save(output_path)
        logger.debug("Edge TTS: saved %d chars → %s", len(text), output_path)
        return output_path

    def synthesize_sync(self, text: str, output_path: str | None = None) -> str:
        """Synchronous wrapper for synthesize."""
        return asyncio.run(self.synthesize(text, output_path))

    async def stream_synthesize(self, text: str):
        """Stream TTS audio chunks from edge-tts.

        Yields raw MP3 byte chunks as they arrive from Microsoft's service.
        """
        import edge_tts

        communicate = edge_tts.Communicate(text=text, voice=self._voice)
        chunk_count = 0
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunk_count += 1
                yield chunk["data"]
        logger.debug("Edge TTS: streamed %d chunks (%d chars)", chunk_count, len(text))
