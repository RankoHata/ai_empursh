"""ToolRegistry — central registry for callable tools the model can invoke."""

import asyncio
import json
import logging
import time
from typing import Any, Optional

from tools.base import ToolDefinition
from tools.notes import NOTE_TOOLS

logger = logging.getLogger(__name__)

# Default timeout for single tool execution (seconds)
DEFAULT_TOOL_TIMEOUT = 30.0


class ToolRegistry:
    """Holds registered ToolDefinitions and dispatches execution.

    Usage::

        registry = ToolRegistry()
        registry.register(search_notes_tool)
        schemas = registry.get_schemas()
        result_json = await registry.execute("search_notes", {"tags": ["工作"]})
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._ws_sender: Optional[Callable[..., Any]] = None  # per-connection WS send_json

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
        if tool.name in self._tools:
            logger.warning("Overwriting existing tool: %s", tool.name)
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def register_all(self, tools: list[ToolDefinition]) -> None:
        """Register multiple tools at once."""
        for t in tools:
            self.register(t)

    def unregister(self, name: str) -> None:
        """Remove a tool by name."""
        self._tools.pop(name, None)

    # ------------------------------------------------------------------
    # Schema generation (OpenAI Chat API format)
    # ------------------------------------------------------------------

    def get_schemas(self, tool_names: Optional[list[str]] = None) -> list[dict[str, Any]]:
        """Generate the ``tools`` parameter for OpenAI chat completions.

        Args:
            tool_names: If given, only return schemas for these tools.
                        If None, return all registered tools.

        Returns:
            List of tool dicts in OpenAI format:
            ``[{"type": "function", "function": {"name": ..., ...}}]``
        """
        names = set(tool_names) if tool_names is not None else set(self._tools.keys())
        schemas = []
        for name in names:
            tool = self._tools.get(name)
            if tool is None:
                logger.warning("Tool '%s' not found in registry, skipping", name)
                continue
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": tool.parameters,
                            "required": tool.required,
                        },
                    },
                }
            )
        return schemas

    def get_for_skill(self, skill: dict) -> list[dict[str, Any]]:
        """Return tool schemas filtered by a skill's ``allowed_tools`` list."""
        allowed = skill.get("allowed_tools", [])
        if not allowed:
            return self.get_schemas()  # no restriction → all tools
        return self.get_schemas(tool_names=allowed)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(self, name: str, args: dict[str, Any]) -> str:
        """Execute a tool by name and return the JSON-encoded result string.

        Handles timeout, exceptions, and unknown tool names gracefully.
        The returned string is suitable for the ``role: "tool"`` message content.
        """
        tool = self._tools.get(name)
        if tool is None:
            logger.warning("Tool execute: unknown tool '%s' requested", name)
            result = {
                "success": False,
                "data": None,
                "count": 0,
                "message": f"未知工具: {name}",
                "error": "unknown_tool",
            }
            return json.dumps(result, ensure_ascii=False)

        logger.debug(
            "Tool execute: %s args=%s",
            name, json.dumps(args, ensure_ascii=False)[:200],
        )
        started = time.monotonic()
        try:
            # Inject per-connection ws_sender so tools can push to frontend
            coro = tool.executor(**args, _ws_sender=self._ws_sender)
            result = await asyncio.wait_for(coro, timeout=DEFAULT_TOOL_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("Tool '%s' timed out after %.1fs", name, DEFAULT_TOOL_TIMEOUT)
            result = {
                "success": False,
                "data": None,
                "count": 0,
                "message": f"工具 '{name}' 执行超时 ({DEFAULT_TOOL_TIMEOUT}s)",
                "error": "timeout",
            }
        except Exception as exc:
            logger.error("Tool '%s' error: %s", name, exc)
            result = {
                "success": False,
                "data": None,
                "count": 0,
                "message": f"工具 '{name}' 执行出错: {exc}",
                "error": str(type(exc).__name__),
            }

        elapsed_ms = int((time.monotonic() - started) * 1000)
        if isinstance(result, dict):
            result["_duration_ms"] = elapsed_ms
        result_json = json.dumps(result, ensure_ascii=False)
        logger.debug(
            "Tool done: %s success=%s duration=%dms result=%s",
            name,
            result.get("success") if isinstance(result, dict) else "?",
            elapsed_ms,
            result_json[:200],
        )
        return result_json

    @property
    def tool_names(self) -> list[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


# ------------------------------------------------------------------
# Singleton factory
# ------------------------------------------------------------------

def create_default_registry() -> ToolRegistry:
    """Create a ToolRegistry pre-loaded with the default note tools."""
    from tools.notes import NOTE_TOOLS
    registry = ToolRegistry()
    registry.register_all(NOTE_TOOLS)
    return registry
