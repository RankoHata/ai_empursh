"""
DeepSeek API streaming chat engine with stop-signal support.

Each WebSocket connection gets its own ChatSession, which maintains
conversation history and coordinates async streaming with cancellation.
"""

import asyncio
import logging
from typing import AsyncGenerator

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ChatSession:
    """Per-connection session holding conversation history and a stop event."""

    def __init__(self, client: AsyncOpenAI, model_name: str, max_rounds: int = 20):
        self._client = client
        self._model_name = model_name
        self._max_messages = max_rounds * 2  # user + assistant per round
        self._history: list[dict[str, str]] = []
        self._stop_event = asyncio.Event()

    def add_user_message(self, content: str) -> None:
        self._history.append({"role": "user", "content": content})
        self._trim()

    def add_assistant_message(self, content: str) -> None:
        self._history.append({"role": "assistant", "content": content})
        self._trim()

    def _trim(self) -> None:
        """Keep only the most recent N messages to stay within context window."""
        if len(self._history) > self._max_messages:
            self._history = self._history[-self._max_messages:]

    def request_stop(self) -> None:
        """Signal the streaming loop to stop."""
        self._stop_event.set()

    def clear_stop(self) -> None:
        """Reset stop event for the next request."""
        self._stop_event.clear()

    def stopped(self) -> bool:
        return self._stop_event.is_set()

    async def stream_chat(self) -> AsyncGenerator[str, None]:
        """
        Stream tokens from DeepSeek API, yielding each content delta.
        Checks self._stop_event before each yield; breaks when set.
        """
        try:
            stream = await self._client.chat.completions.create(
                model=self._model_name,
                messages=self._history,
                stream=True,
                stream_options={"include_usage": True},
            )
        except Exception as exc:
            logger.error("Failed to create chat completion: %s", exc)
            raise

        collected: list[str] = []
        try:
            async for chunk in stream:
                if self._stop_event.is_set():
                    logger.info("Chat streaming stopped by user request")
                    break

                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    collected.append(delta.content)
                    yield delta.content
        finally:
            # Close the stream to free resources
            await stream.close()

        full_text = "".join(collected)
        if full_text:
            self.add_assistant_message(full_text)
