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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _history_summary(history: list[dict[str, Any]]) -> str:
    """One-line summary of history message roles for debug logging."""
    roles = []
    for m in history:
        r = m.get("role", "?")
        if r == "assistant" and m.get("tool_calls"):
            r = "assistant[tool_calls]"
        elif r == "tool":
            r = f"tool(id={m.get('tool_call_id','?')[:8]})"
        roles.append(r)
    return " → ".join(roles) if roles else "(empty)"


# ---------------------------------------------------------------------------
# ChatSession
# ---------------------------------------------------------------------------

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
        self._max_messages = max_rounds * 6  # user + assistant + tool_calls per round
        self._history: list[dict[str, Any]] = []
        self._stop_event = asyncio.Event()
        self._tool_registry = tool_registry
        self._on_tool_call = on_tool_call
        self._on_tool_result = on_tool_result
        self._max_tool_rounds = max_tool_rounds
        self._trace: list[dict[str, Any]] = []  # current turn trace

        logger.debug(
            "ChatSession created: model=%s max_rounds=%d max_messages=%d "
            "max_tool_rounds=%d has_tools=%s",
            model_name, max_rounds, self._max_messages,
            max_tool_rounds, tool_registry is not None,
        )

    # ------------------------------------------------------------------
    # History management
    # ------------------------------------------------------------------

    def add_user_message(self, content: str) -> None:
        logger.debug("History ← user (%d chars): %s", len(content), content[:80])
        self._history.append({"role": "user", "content": content})
        self._trim()

    def add_system_message(self, content: str) -> None:
        """Inject a system message into history (e.g. tool-loop limit warning)."""
        logger.debug("History ← system: %s", content[:80])
        self._history.append({"role": "system", "content": content})
        self._trim()

    def add_assistant_message(self, content: str) -> None:
        logger.debug("History ← assistant (%d chars): %s", len(content), content[:80])
        self._history.append({"role": "assistant", "content": content})
        self._trim()

    def _trim(self) -> None:
        """Keep only the most recent N messages; never orphan tool results."""
        before = len(self._history)
        if before <= self._max_messages:
            return
        self._history = self._history[-self._max_messages:]
        # Drop leading orphaned tool messages (their tool_calls was trimmed off)
        orphaned = 0
        while self._history and self._history[0].get("role") == "tool":
            self._history.pop(0)
            orphaned += 1
        if orphaned:
            logger.debug(
                "History trimmed: %d → %d messages (dropped %d orphaned tool msgs)",
                before, len(self._history), orphaned,
            )

    # ------------------------------------------------------------------
    # Stop signal
    # ------------------------------------------------------------------

    def request_stop(self) -> None:
        """Signal the streaming loop to stop."""
        logger.debug("Stop requested")
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
        msg_count = len(self._history)
        logger.debug(
            "API call (no tools): model=%s messages=%d history=[%s]",
            self._model_name, msg_count, _history_summary(self._history),
        )
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
        chunk_count = 0
        try:
            async for chunk in stream:
                if self._stop_event.is_set():
                    logger.info("Chat streaming stopped by user request")
                    break

                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    collected.append(delta.content)
                    chunk_count += 1
                    yield delta.content
        finally:
            await stream.close()

        full_text = "".join(collected)
        logger.debug(
            "API done (no tools): tokens=%d content_chars=%d finish_reason=%s",
            chunk_count, len(full_text),
            "stopped" if self._stop_event.is_set() else "stop",
        )
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
        tool_calls_yielded: bool = False

        tool_names = [t["function"]["name"] for t in tool_schemas]
        logger.debug(
            "API call (with tools): model=%s messages=%d tools=%s history=[%s]",
            self._model_name, len(self._history), tool_names,
            _history_summary(self._history),
        )

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

        content_count = 0
        try:
            async for chunk in stream:
                if self._stop_event.is_set():
                    logger.info("Tool chat stopped by user")
                    accumulated_content.clear()
                    accumulated_tool_calls.clear()
                    break

                delta = chunk.choices[0].delta if chunk.choices else None
                finish_reason = chunk.choices[0].finish_reason if chunk.choices else None

                # --- content tokens ---
                if delta and delta.content:
                    accumulated_content.append(delta.content)
                    content_count += 1
                    yield ("content", delta.content)

                # --- tool_call tokens (may arrive interleaved with content) ---
                if delta and delta.tool_calls:
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
                            logger.debug(
                                "Tool call fragment [idx=%d]: new call id=%s",
                                idx, tc_delta.id,
                            )
                        entry = accumulated_tool_calls[idx]
                        if tc_delta.id:
                            entry["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                entry["function"]["name"] += tc_delta.function.name
                            if tc_delta.function.arguments:
                                entry["function"]["arguments"] += tc_delta.function.arguments

                # --- stream finished with tool_calls ---
                if finish_reason == "tool_calls" and accumulated_tool_calls and not tool_calls_yielded:
                    tool_calls_yielded = True

                    # MUST write assistant(tool_calls) to history BEFORE yielding,
                    # because the caller will immediately execute tools and append
                    # role:"tool" results — which must come AFTER tool_calls.
                    tool_call_blocks = []
                    for idx in sorted(accumulated_tool_calls):
                        tc = accumulated_tool_calls[idx]
                        tool_call_blocks.append({
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"]["arguments"],
                            },
                        })
                    full_text = "".join(accumulated_content)
                    assistant_msg: dict[str, Any] = {
                        "role": "assistant",
                        "tool_calls": tool_call_blocks,
                    }
                    if full_text:
                        assistant_msg["content"] = full_text

                    logger.debug(
                        "History ← assistant[tool_calls] (%d calls): %s",
                        len(tool_call_blocks),
                        [(b["function"]["name"], b["function"]["arguments"][:80])
                         for b in tool_call_blocks],
                    )
                    self._history.append(assistant_msg)

                    for idx in sorted(accumulated_tool_calls):
                        tc = accumulated_tool_calls[idx]
                        func = tc["function"]
                        logger.debug(
                            "Yield tool_call: name=%s id=%s args=%s",
                            func["name"], tc["id"], func["arguments"][:120],
                        )
                        yield ("tool_call", {
                            "id": tc["id"],
                            "name": func["name"],
                            "arguments": func["arguments"],
                        })

        finally:
            await stream.close()

        # Add pure-text assistant message to history (tool_calls already handled above)
        if not tool_calls_yielded:
            full_text = "".join(accumulated_content)
            logger.debug(
                "API done (with tools): content_tokens=%d finish_reason=%s text_chars=%d",
                content_count,
                "stopped" if self._stop_event.is_set() else "stop",
                len(full_text),
            )
            if full_text:
                self.add_assistant_message(full_text)
        else:
            logger.debug(
                "API done (with tools): tool_calls yielded=%d content_tokens=%d",
                len(accumulated_tool_calls), content_count,
            )

    # ------------------------------------------------------------------
    # Full tool loop (multi-turn)
    # ------------------------------------------------------------------

    async def stream_with_tool_loop(
        self,
        tool_schemas: list[dict[str, Any]],
    ) -> AsyncGenerator[Tuple[str, Any], None]:
        """High-level: stream chat, execute tools, loop until text-only response.

        Records a structured trace for debugging and persistence.
        """
        self._trace = []  # fresh trace for this turn

        if self._tool_registry is None:
            logger.debug("Tool loop: no registry, falling back to stream_chat")
            async for token in self.stream_chat():
                yield ("content", token)
            return

        tool_round = 0
        logger.debug("Tool loop start: max_rounds=%d tools=%d",
                     self._max_tool_rounds, len(tool_schemas))

        while tool_round < self._max_tool_rounds:
            if self._stop_event.is_set():
                self._trace.append({"step": "stopped", "round": tool_round})
                logger.debug("Tool loop: stopped at round %d", tool_round)
                break

            had_tool_call = False
            self._trace.append({
                "step": "api_call",
                "round": tool_round,
                "tools": [t["function"]["name"] for t in tool_schemas],
                "history_msgs": len(self._history),
            })
            logger.debug("Tool loop round %d: calling stream_chat_with_tools", tool_round)

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
                        logger.warning(
                            "Tool call '%s': invalid JSON args: %s",
                            tool_name, data["arguments"][:120],
                        )
                        tool_args = {}

                    self._trace.append({
                        "step": "tool_call",
                        "round": tool_round,
                        "name": tool_name,
                        "id": tool_call_id,
                        "args": tool_args,
                    })

                    # Notify callback
                    if self._on_tool_call:
                        try:
                            await self._on_tool_call(tool_name, tool_args)
                        except Exception as exc:
                            logger.error("on_tool_call error: %s", exc)

                    # Execute
                    result_json = await self._tool_registry.execute(tool_name, tool_args)
                    result_dict = json.loads(result_json)

                    self._trace.append({
                        "step": "tool_result",
                        "round": tool_round,
                        "name": tool_name,
                        "id": tool_call_id,
                        "success": result_dict.get("success"),
                        "message": result_dict.get("message", ""),
                        "duration_ms": result_dict.pop("_duration_ms", 0),
                        "count": result_dict.get("count", 0),
                    })

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
                self._trace.append({"step": "done", "round": tool_round})
                logger.debug("Tool loop: no tool calls in round %d, done", tool_round)
                break

            tool_round += 1
            logger.debug("Tool loop: advancing to round %d", tool_round)

        if tool_round >= self._max_tool_rounds:
            self._trace.append({"step": "max_rounds_reached", "round": tool_round})
            logger.warning("Tool loop reached max rounds (%d), forcing reply", self._max_tool_rounds)
            self.add_system_message("已达到最大工具调用次数。请基于已有信息直接回复用户，不要再调用工具。")
            async for token in self.stream_chat():
                yield ("content", token)

    # ------------------------------------------------------------------
    # Trace & history export/import (for persistence + debugging)
    # ------------------------------------------------------------------

    def get_trace(self) -> list[dict[str, Any]]:
        """Return the structured trace for the most recent turn."""
        return self._trace

    def export_history(self) -> list[dict[str, Any]]:
        """Return a JSON-serializable copy of the conversation history."""
        return list(self._history)

    def load_history(self, messages: list[dict[str, Any]]) -> None:
        """Restore conversation history from a saved messages array."""
        self._history = list(messages)
        logger.debug("History loaded: %d messages", len(self._history))

    def add_tool_result(self, tool_call_id: str, result_json: str) -> None:
        """Manually add a tool result message to history."""
        logger.debug(
            "History ← tool(%s) [manual]: %s",
            tool_call_id[:8], result_json[:120],
        )
        self._history.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result_json,
        })
