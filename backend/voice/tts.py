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

    if engine_type == "xtts":
        xtts_cfg = voice_cfg.get("xtts", {})
        try:
            from voice.tts_xtts import XTTSEngine
            _engine = XTTSEngine(
                reference_audio=xtts_cfg.get("reference_audio", ""),
                language=xtts_cfg.get("language", "zh-cn"),
                use_gpu=xtts_cfg.get("use_gpu", True),
            )
            logger.info("TTS engine: XTTS-v2")
        except ImportError as exc:
            logger.warning(
                "XTTS-v2 not available (%s), falling back to edge-tts. "
                "Install with: uv sync --extra tts-xtts", exc,
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
