"""
Text-to-speech using F5-TTS (zero-shot voice cloning, cross-lingual).

Requirements: pip install f5-tts
Model: ~1GB, downloads from HuggingFace on first use (auto-cached).

Voice cloning: provide a 5-10s reference WAV + its transcript.
The model clones the speaker's voice across languages (e.g. Japanese voice → Chinese).
"""

import io
import logging
import os
import wave
from pathlib import Path
from typing import Optional

# Force torchaudio to use soundfile backend on Windows (avoids torchcodec/FFmpeg issues)
if os.name == "nt":
    os.environ["TORCHAUDIO_USE_SOUNDFILE_LEGACY_INTERFACE"] = "1"

from voice.tts_base import BaseTTSEngine

logger = logging.getLogger(__name__)

TEMP_DIR = Path(__file__).parent.parent / "temp"


class F5TTSEngine(BaseTTSEngine):
    """F5-TTS — zero-shot voice cloning, cross-lingual, fast inference."""

    def __init__(
        self,
        reference_audio: str = "",
        reference_text: str = "",
        language: str = "zh",
        use_gpu: bool = True,
    ) -> None:
        self._ref_audio = reference_audio
        self._ref_text = reference_text
        self._language = language
        self._use_gpu = use_gpu
        self._model = None  # lazy-loaded
        logger.info(
            "F5TTSEngine created: ref_audio=%s lang=%s gpu=%s",
            reference_audio or "(none)", language, use_gpu,
        )

    # ------------------------------------------------------------------
    # Engine metadata
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "f5-tts"

    @property
    def sample_rate(self) -> int:
        return 24000

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    def _has_ref_audio(self) -> bool:
        return bool(self._ref_audio and os.path.exists(self._ref_audio))

    def _load_model(self):
        """Lazy-load the F5-TTS model. Downloads from HF on first call (~1 GB)."""
        if self._model is not None:
            return

        logger.info("Loading F5-TTS model (first call, downloads ~1 GB if not cached)...")
        try:
            import torch
            from f5_tts.api import F5TTS

            device = "cuda" if self._use_gpu and torch.cuda.is_available() else "cpu"
            if self._use_gpu and device == "cpu":
                logger.info("CUDA not available, falling back to CPU")

            self._model = F5TTS(device=device)
            logger.info("F5-TTS model loaded on %s", device)
        except Exception as exc:
            raise RuntimeError(
                f"F5-TTS failed to load: {exc}. Install with: uv sync --extra tts-f5"
            ) from exc

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    async def synthesize(self, text: str, output_path: str | None = None) -> str:
        self._load_model()

        if output_path is None:
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            output_path = str(TEMP_DIR / f"tts_{os.urandom(6).hex()}.wav")

        ref_audio = self._ref_audio if self._has_ref_audio() else None
        ref_text = self._ref_text if ref_audio and self._ref_text else None

        import asyncio
        loop = asyncio.get_running_loop()
        wav, sr, _ = await loop.run_in_executor(
            None,
            lambda: self._model.infer(
                ref_file=ref_audio,
                ref_text=ref_text or "",  # empty string = model uses audio only
                gen_text=text,
            ),
        )

        # Save to WAV
        import torch
        if isinstance(wav, torch.Tensor):
            wav = wav.cpu().numpy()
        self._save_wav(output_path, wav, sr)
        logger.debug("F5-TTS: saved %d chars → %s", len(text), output_path)
        return output_path

    async def stream_synthesize(self, text: str):
        """Stream-synthesize: generate full audio, yield in 8 KB chunks."""
        self._load_model()

        ref_audio = self._ref_audio if self._has_ref_audio() else None
        ref_text = self._ref_text if ref_audio and self._ref_text else None

        import asyncio
        import torch
        loop = asyncio.get_running_loop()

        wav, sr, _ = await loop.run_in_executor(
            None,
            lambda: self._model.infer(
                ref_file=ref_audio,
                ref_text=ref_text or "",
                gen_text=text,
            ),
        )

        if isinstance(wav, torch.Tensor):
            wav = wav.cpu().numpy()

        wav_bytes = self._numpy_to_wav_bytes(wav, sr)
        chunk_size = 8192
        total = 0
        for offset in range(0, len(wav_bytes), chunk_size):
            chunk = wav_bytes[offset:offset + chunk_size]
            total += len(chunk)
            yield chunk
        logger.debug("F5-TTS: streamed %d bytes (%d chars)", total, len(text))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _numpy_to_wav_bytes(audio, sample_rate: int) -> bytes:
        """Convert float32 numpy array [-1, 1] to WAV bytes."""
        import numpy as np
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            audio_int16 = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
            wf.writeframes(audio_int16.tobytes())
        return buf.getvalue()

    @staticmethod
    def _save_wav(path: str, audio, sample_rate: int) -> None:
        """Save numpy array to WAV file."""
        wav_bytes = F5TTSEngine._numpy_to_wav_bytes(audio, sample_rate)
        with open(path, "wb") as f:
            f.write(wav_bytes)
