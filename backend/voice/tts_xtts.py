"""
Text-to-speech using Coqui XTTS-v2 (local voice cloning).

Requirements: xtts-api-server (or coqui-tts/TTS) + torch
First run downloads the model (~1.8 GB) from HuggingFace.

Voice cloning: provide a 5-10s reference WAV file.
The model clones the speaker's voice and synthesizes in that style.

Install: uv sync --extra tts-xtts
"""

import io
import logging
import os
import wave
from pathlib import Path
from typing import Optional

from voice.tts_base import BaseTTSEngine

logger = logging.getLogger(__name__)

TEMP_DIR = Path(__file__).parent.parent / "temp"
DEFAULT_LANGUAGE = "zh-cn"

# XTTS-v2 model supports these languages (use ISO codes for best results)
# Full list: en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh-cn, hu, ko, ja, hi
SUPPORTED_LANGUAGES = {
    "zh": "zh-cn", "zh-cn": "zh-cn", "中文": "zh-cn",
    "en": "en", "英文": "en", "英语": "en",
    "ja": "ja", "日文": "ja", "日语": "ja",
    "ko": "ko", "韩语": "ko", "韩文": "ko",
    "auto": "zh-cn",  # default
}


class XTTSEngine(BaseTTSEngine):
    """Coqui XTTS-v2 — local voice cloning, streaming, GPU optional."""

    def __init__(
        self,
        reference_audio: str = "",
        language: str = DEFAULT_LANGUAGE,
        use_gpu: bool = True,
    ) -> None:
        self._ref_audio = reference_audio
        self._language = SUPPORTED_LANGUAGES.get(language, DEFAULT_LANGUAGE)
        self._use_gpu = use_gpu
        self._model = None  # lazy-loaded
        logger.info(
            "XTTSEngine created: ref_audio=%s lang=%s gpu=%s",
            reference_audio or "(none, will use default speaker)",
            self._language, use_gpu,
        )

    # ------------------------------------------------------------------
    # Engine metadata
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "xtts-v2"

    @property
    def sample_rate(self) -> int:
        return 24000

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    def _load_model(self):
        """Lazy-load the XTTS-v2 model. Called on first synthesis."""
        if self._model is not None:
            return

        logger.info("Loading XTTS-v2 model (first call, ~1.8 GB download if not cached)...")

        # Try multiple import paths (coqui-tts installs as 'TTS', xtts-api-server
        # depends on coqui-tts which also installs as 'TTS').
        TTS = None
        for pkg_name in ("TTS", "coqui_tts"):
            try:
                mod = __import__(f"{pkg_name}.api", fromlist=["TTS"])
                TTS = getattr(mod, "TTS", None)
                if TTS is not None:
                    break
            except ImportError:
                continue

        if TTS is None:
            raise RuntimeError(
                "XTTS-v2 requires coqui-tts (or the xtts-api-server package). "
                "Install with: uv sync --extra tts-xtts"
            )

        try:
            device = "cuda" if self._use_gpu else "cpu"
            self._model = TTS(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                progress_bar=False,
            )
            self._model.to(device)
            logger.info("XTTS-v2 model loaded on %s", device)
        except Exception as exc:
            logger.error("Failed to load XTTS-v2 model: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    async def synthesize(self, text: str, output_path: str | None = None) -> str:
        """Synthesize text to a WAV file. Returns the file path."""
        self._load_model()

        if output_path is None:
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            output_path = str(TEMP_DIR / f"tts_{os.urandom(6).hex()}.wav")

        # Determine speaker reference
        speaker_wav = self._ref_audio if self._ref_audio and os.path.exists(self._ref_audio) else None

        # Run in thread (TTS library is synchronous)
        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._model.tts_to_file(
                text=text,
                speaker_wav=speaker_wav,
                language=self._language,
                file_path=output_path,
            ),
        )
        logger.debug("XTTS: saved %d chars → %s", len(text), output_path)
        return output_path

    async def stream_synthesize(self, text: str):
        """Stream-synthesize text, yielding WAV byte chunks.

        XTTS generates audio in chunks internally. We accumulate and yield
        as PCM frames, wrapped in a streaming WAV-like format for the
        browser's <audio> element. For simplicity, we yield the full WAV
        in chunks since the browser can play partial WAV data.
        """
        self._load_model()

        speaker_wav = self._ref_audio if self._ref_audio and os.path.exists(self._ref_audio) else None

        # Generate full audio in a temp buffer, then stream it in chunks
        import asyncio
        loop = asyncio.get_running_loop()

        # Generate WAV bytes
        wav_bytes = await loop.run_in_executor(
            None,
            lambda: self._generate_wav_bytes(text, speaker_wav),
        )

        # Stream in 8 KB chunks
        chunk_size = 8192
        for offset in range(0, len(wav_bytes), chunk_size):
            yield wav_bytes[offset:offset + chunk_size]

        logger.debug("XTTS: streamed %d chunks (%d chars)", (len(wav_bytes) + 8191) // 8192, len(text))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _generate_wav_bytes(self, text: str, speaker_wav: Optional[str]) -> bytes:
        """Generate WAV audio bytes (in-memory)."""
        import numpy as np
        # Synthesize to numpy array
        wav_np = self._model.tts(
            text=text,
            speaker_wav=speaker_wav,
            language=self._language,
        )
        # wav_np is a numpy array of float32 samples
        return self._numpy_to_wav_bytes(wav_np, self.sample_rate)

    @staticmethod
    def _numpy_to_wav_bytes(audio: "np.ndarray", sample_rate: int) -> bytes:
        """Convert float32 numpy array [-1, 1] to WAV bytes."""
        import numpy as np
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            # Convert float32 to int16 PCM
            audio_int16 = (audio * 32767).astype(np.int16)
            wf.writeframes(audio_int16.tobytes())
        return buf.getvalue()
