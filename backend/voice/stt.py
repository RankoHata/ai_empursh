"""
Speech-to-text using faster-whisper (local model, CUDA accelerated).
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_engine = None  # singleton


def get_engine(model_size: str = "base", device: str = "auto"):
    """Lazy-load the faster-whisper model. Cached after first call."""
    global _engine
    if _engine is not None:
        return _engine

    # Resolve device: prefer CUDA if available
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    logger.info("Loading faster-whisper model '%s' on %s ...", model_size, device)
    from faster_whisper import WhisperModel

    _engine = WhisperModel(
        model_size,
        device=device,
        compute_type="float16" if device == "cuda" else "int8",
        download_root=str(Path(__file__).parent.parent / "models"),
    )
    logger.info("faster-whisper model loaded")
    return _engine


def transcribe(audio_path: str, model_size: str = "base") -> str:
    """Transcribe a WAV audio file to text. Returns the recognized text."""
    engine = get_engine(model_size=model_size)
    segments, info = engine.transcribe(audio_path, beam_size=5, language="zh")
    parts = [seg.text.strip() for seg in segments]
    text = "".join(parts)
    logger.info("STT result: %s", text[:100] if len(text) > 100 else text)
    return text


def vad_detect(audio_bytes: bytes, threshold_rms: float = 0.02) -> bool:
    """Simple energy-based voice activity detection.
    
    Returns True if the audio chunk contains speech (RMS > threshold).
    """
    import array
    import math

    # Convert raw PCM 16-bit to samples
    if len(audio_bytes) < 2:
        return False
    samples = array.array("h", audio_bytes)
    if len(samples) == 0:
        return False
    rms = math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0
    return rms > threshold_rms
