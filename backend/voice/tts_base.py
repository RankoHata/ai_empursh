"""Abstract base class for TTS engines."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseTTSEngine(ABC):
    """Pluggable TTS backend.

    Subclasses: EdgeTTSEngine (Microsoft edge-tts), XTTSEngine (Coqui XTTS-v2).
    """

    @abstractmethod
    async def synthesize(self, text: str, output_path: str) -> str:
        """Synthesize text to an audio file. Returns the file path."""
        ...

    @abstractmethod
    async def stream_synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Stream-synthesize text, yielding audio chunks (MP3 or WAV bytes)."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable engine name."""
        ...

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Output sample rate."""
        ...
