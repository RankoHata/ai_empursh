"""
TTS engine factory — returns the configured engine instance.

Keeps backward-compatible module-level functions: synthesize(), stream_synthesize().
These delegate to the current engine, which can be swapped at runtime.
"""

import logging
from typing import Optional

from voice.tts_base import BaseTTSEngine
from voice.tts_edge import EdgeTTSEngine, DEFAULT_VOICE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global engine instance (swappable at runtime)
# ---------------------------------------------------------------------------

_engine: Optional[BaseTTSEngine] = None
_engine_name: str = "edge"  # default fallback


def get_engine() -> BaseTTSEngine:
    """Return the current TTS engine (lazy-init edge-tts as fallback)."""
    global _engine
    if _engine is None:
        logger.info("No TTS engine configured, using edge-tts fallback")
        _engine = EdgeTTSEngine(voice=DEFAULT_VOICE)
    return _engine


def configure_engine(config: dict) -> BaseTTSEngine:
    """Create and set the TTS engine from config.

    config['voice'] dict:
        tts_engine:  "edge" | "xtts"  (default: "edge")
        tts_voice:   voice name for edge-tts (default: zh-CN-XiaoxiaoNeural)
        xtts:
            reference_audio: path to WAV for voice cloning
            language:        "zh-cn" | "en" | ...
            use_gpu:         true | false
    """
    global _engine, _engine_name
    voice_cfg = config.get("voice", {})
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
            _engine_name = "xtts"
            logger.info("TTS engine: XTTS-v2 (voice cloning)")
        except ImportError as exc:
            logger.warning(
                "XTTS-v2 not available (%s), falling back to edge-tts. "
                "Install with: pip install TTS torch", exc,
            )
            voice = voice_cfg.get("tts_voice", DEFAULT_VOICE)
            _engine = EdgeTTSEngine(voice=voice)
            _engine_name = "edge"
    else:
        voice = voice_cfg.get("tts_voice", DEFAULT_VOICE)
        _engine = EdgeTTSEngine(voice=voice)
        _engine_name = "edge"
        logger.info("TTS engine: edge-tts (voice=%s)", voice)

    return _engine


def get_engine_name() -> str:
    """Return the current engine type name."""
    return _engine_name


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
