"""
TTS engine factory — creates and manages the configured TTS engine.

Uses the AppConfig singleton for configuration. The engine is created
at startup via configure_engine() and can be swapped by re-calling it.
"""

import logging
from typing import Optional

from config import config
from voice.tts_base import BaseTTSEngine
from voice.tts_edge import EdgeTTSEngine, DEFAULT_VOICE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global engine instance (swappable at runtime)
# ---------------------------------------------------------------------------

_engine: Optional[BaseTTSEngine] = None


def get_engine() -> BaseTTSEngine:
    """Return the current TTS engine (lazy-init edge-tts as fallback)."""
    global _engine
    if _engine is None:
        logger.info("No TTS engine configured, using edge-tts fallback")
        _engine = EdgeTTSEngine(voice=DEFAULT_VOICE)
    return _engine


def configure_engine() -> BaseTTSEngine:
    """Create and set the TTS engine from the config singleton."""
    global _engine
    voice_cfg = config.voice
    engine_type = voice_cfg.get("tts_engine", "edge").lower()

    if engine_type == "f5":
        f5_cfg = voice_cfg.get("f5", {})
        try:
            from voice.tts_f5 import F5TTSEngine
            _engine = F5TTSEngine(
                reference_audio=f5_cfg.get("reference_audio", ""),
                reference_text=f5_cfg.get("reference_text", ""),
                language=f5_cfg.get("language", "zh"),
                use_gpu=f5_cfg.get("use_gpu", True),
            )
            logger.info("TTS engine: F5-TTS")
        except ImportError as exc:
            logger.warning(
                "F5-TTS not available (%s), falling back to edge-tts. "
                "Install with: uv sync --extra tts-f5", exc,
            )
            _engine = EdgeTTSEngine(voice=voice_cfg.get("tts_voice", DEFAULT_VOICE))
    else:
        _engine = EdgeTTSEngine(voice=voice_cfg.get("tts_voice", DEFAULT_VOICE))
        logger.info("TTS engine: edge-tts")

    return _engine


def get_engine_name() -> str:
    """Return the current engine type name."""
    return get_engine().name


# ---------------------------------------------------------------------------
# Backward-compatible module-level functions
# ---------------------------------------------------------------------------

async def synthesize(text: str, output_path: str | None = None) -> str:
    """Convert text to speech using the current engine."""
    return await get_engine().synthesize(text, output_path)


async def stream_synthesize(text: str):
    """Stream-synthesize text using the current engine."""
    async for chunk in get_engine().stream_synthesize(text):
        yield chunk
