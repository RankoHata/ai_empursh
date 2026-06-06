"""
DeepSeek API streaming chat engine with stop-signal and tool-calling support.

Each WebSocket connection gets its own ChatSession, which maintains
conversation history and coordinates async streaming with cancellation.
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Callable, Optional, Tuple

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ChatSession:
    """Per-connection session holding conversation history and a stop event."""

    def __init__(
        self,
        client: AsyncOpenAI,
        model_name: str,
        max_rounds: int = 20,
        tool_registry: Any = None,
        on_tool_call: Optional[Callable[..., Any]] = None,
        on_tool_result: Optional[Callable[..., Any]] = None,
        max_tool_rounds: int = 10,
    ):
        self._client = client
        self._model_name = model_name
        self._max_messages = max_rounds * 2  # user + assistant per round
        self._history: list[dict[str, Any]] = []
        self._stop_event = asyncio.Event()
        self._tool_registry = tool_registry
        self._on_tool_call = on_tool_call
        self._on_tool_result = on_tool_result
        self._max_tool_rounds = max_tool_rounds

    # ------------------------------------------------------------------
    # History management
    # ------------------------------------------------------------------

    def add_user_message(self, content: str) -> None:
        self._history.append({"role": "user", "content": content})
        self._trim()

    def add_system_message(self, content: str) -> None:
        """Inject a system message into history (e.g. tool-loop limit warning)."""
        self._history.append({"role": "system", "content": content})
        self._trim()

    def add_assistant_message(self, content: str) -> None:
        self._history.append({"role": "assistant", "content": content})
        self._trim()

    def _trim(self) -> None:
        """Keep only the most recent N messages to stay within context window."""
        if len(self._history) > self._max_messages:
            self._history = self._history[-self._max_messages:]

    # ------------------------------------------------------------------
    # Stop signal
    # ------------------------------------------------------------------

    def request_stop(self) -> None:
        """Signal the streaming loop to stop."""
        self._stop_event.set()

    def clear_stop(self) -> None:
        """Reset stop event for the next request."""
        self._stop_event.clear()

    def stopped(self) -> bool:
        return self._stop_event.is_set()

    # ------------------------------------------------------------------
    # Simple streaming (no tools) — unchanged from original
    # ------------------------------------------------------------------

    async def stream_chat(self) -> AsyncGenerator[str, None]:
        """Stream tokens without tool definitions. Backward-compatible."""
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
            await stream.close()

        full_text = "".join(collected)
        if full_text:
            self.add_assistant_message(full_text)

    # ------------------------------------------------------------------
    # Tool-calling streaming
    # ------------------------------------------------------------------

    async def stream_chat_with_tools(
        self,
        tool_schemas: list[dict[str, Any]],
    ) -> AsyncGenerator[Tuple[str, Any], None]:
        """Stream chat with tool definitions.

        Yields ``("content", str)`` for text tokens and
        ``("tool_call", dict)`` for tool invocations.

        Tool call dict: {"id": str, "name": str, "arguments": str (JSON)}
        """
        accumulated_content: list[str] = []
        accumulated_tool_calls: dict[int, dict[str, Any]] = {}
        finish_reason: Optional[str] = None

        try:
            stream = await self._client.chat.completions.create(
                model=self._model_name,
                messages=self._history,
                tools=tool_schemas,
                stream=True,
                stream_options={"include_usage": True},
            )
        except Exception as exc:
            logger.error("Failed to create chat completion with tools: %s", exc)
            raise

        try:
            async for chunk in stream:
                if self._stop_event.is_set():
                    logger.info("Tool chat stopped by user")
                    accumulated_content.clear()
                    accumulated_tool_calls.clear()
                    break

                delta = chunk.choices[0].delta if chunk.choices else None
                finish_reason = chunk.choices[0].finish_reason if chunk.choices else None

                if delta is None:
                    continue

                # --- content tokens ---
                if delta.content:
                    accumulated_content.append(delta.content)
                    yield ("content", delta.content)

                # --- tool_call tokens (may arrive interleaved with content) ---
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc_delta.id or "",
                                "function": {
                                    "name": "",
                                    "arguments": "",
                                },
                            }
                        entry = accumulated_tool_calls[idx]
                        if tc_delta.id:
                            entry["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                entry["function"]["name"] += tc_delta.function.name
                            if tc_delta.function.arguments:
                                entry["function"]["arguments"] += tc_delta.function.arguments

                # --- stream finished with tool_calls ---
                if finish_reason == "tool_calls" and accumulated_tool_calls:
                    for tc in sorted(accumulated_tool_calls.values(), key=lambda x: x["id"]):
                        func = tc["function"]
                        yield ("tool_call", {
                            "id": tc["id"],
                            "name": func["name"],
                            "arguments": func["arguments"],
                        })

        finally:
            await stream.close()

        # Add to history
        full_text = "".join(accumulated_content)
        if accumulated_tool_calls:
            tool_call_blocks = []
            for tc in sorted(accumulated_tool_calls.values(), key=lambda x: x["id"]):
                tool_call_blocks.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                })
            self._history.append({
                "role": "assistant",
                "content": full_text if full_text else None,
                "tool_calls": tool_call_blocks,
            })
        elif full_text:
            self.add_assistant_message(full_text)

    # ------------------------------------------------------------------
    # Full tool loop (multi-turn)
    # ------------------------------------------------------------------

    async def stream_with_tool_loop(
        self,
        tool_schemas: list[dict[str, Any]],
    ) -> AsyncGenerator[Tuple[str, Any], None]:
        """High-level: stream chat, execute tools, loop until text-only response.

        Wraps ``stream_chat_with_tools()`` and handles the entire
        tool-calling lifecycle internally. The caller only needs to yield
        events to the frontend.
        """
        if self._tool_registry is None:
            async for token in self.stream_chat():
                yield ("content", token)
            return

        tool_round = 0

        while tool_round < self._max_tool_rounds:
            if self._stop_event.is_set():
                break

            had_tool_call = False

            async for event_type, data in self.stream_chat_with_tools(tool_schemas):
                if event_type == "content":
                    yield ("content", data)
                elif event_type == "tool_call":
                    had_tool_call = True
                    tool_name = data["name"]
                    tool_call_id = data["id"]

                    # Parse arguments (model returns JSON string)
                    try:
                        tool_args = json.loads(data["arguments"])
                    except json.JSONDecodeError:
                        tool_args = {}

                    # Notify callback
                    if self._on_tool_call:
                        try:
                            await self._on_tool_call(tool_name, tool_args)
                        except Exception as exc:
                            logger.error("on_tool_call error: %s", exc)

                    # Execute
                    result_json = await self._tool_registry.execute(tool_name, tool_args)
                    result_dict = json.loads(result_json)

                    # Notify callback
                    if self._on_tool_result:
                        try:
                            await self._on_tool_result(tool_name, result_dict)
                        except Exception as exc:
                            logger.error("on_tool_result error: %s", exc)

                    # Feed result back to history
                    self._history.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": result_json,
                    })

            if not had_tool_call:
                break

            tool_round += 1

        if tool_round >= self._max_tool_rounds:
            logger.warning("Tool loop reached max rounds (%d), forcing reply", self._max_tool_rounds)
            self.add_system_message("已达到最大工具调用次数。请基于已有信息直接回复用户，不要再调用工具。")
            async for token in self.stream_chat():
                yield ("content", token)

    # ------------------------------------------------------------------
    # Tool result injection (for manual loop control)
    # ------------------------------------------------------------------

    def add_tool_result(self, tool_call_id: str, result_json: str) -> None:
        """Manually add a tool result message to history."""
        self._history.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result_json,
        })
