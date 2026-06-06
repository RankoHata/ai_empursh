# Tool Calling 系统 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 AI 桌面助理添加 OpenAI function calling 能力，使模型能自主调用 search_notes/get_notes/add_note 工具，替代手动数据注入。

**Architecture:** 新增 `backend/tools/` 包（ToolRegistry + ToolDefinition），ChatSession 增加 `stream_chat_with_tools()` 多轮 tool loop，main.py 注册工具并推送 tool_call 事件到前端，前端新增 ToolCallCard 组件展示可展开工具调用卡片。

**Tech Stack:** Python 3.10+ (async/await, dataclasses, Optional types), React 18+ JSX, WebSocket JSON, OpenAI-compatible API (DeepSeek)

**Design spec:** `docs/superpowers/specs/2026-06-06-tool-calling-system-design.md`

---

### Task 1: Create ToolDefinition dataclass

**Files:**
- Create: `backend/tools/__init__.py` (empty)
- Create: `backend/tools/base.py`

- [ ] **Step 1: Create empty tools package `__init__.py`**

```bash
mkdir -p backend/tools
```

- [ ] **Step 2: Write `backend/tools/base.py`**

```python
"""ToolDefinition — data class describing a callable tool for the model."""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ToolDefinition:
    """Describes a function the model can call.

    Attributes:
        name:        Unique tool identifier, e.g. "search_notes".
        description: Natural-language description for the model.
        parameters:  JSON Schema ``properties`` dict (keys are param names).
        required:    List of required parameter names.
        executor:    Async callable that receives **kwargs and returns a dict.
        display_name:Human-readable label for the frontend (defaults to name).
    """

    name: str
    description: str
    parameters: dict[str, Any]
    required: list[str]
    executor: Callable[..., Any]  # async (**_kw) -> dict
    display_name: str = ""

    def __post_init__(self) -> None:
        if not self.display_name:
            self.display_name = self.name
```

- [ ] **Step 3: Commit**

```bash
git add backend/tools/__init__.py backend/tools/base.py
git commit -m "feat: add ToolDefinition dataclass to tools package"
```

---

### Task 2: Define note tools

**Files:**
- Create: `backend/tools/notes.py`
- Modify: `backend/tools/__init__.py`

- [ ] **Step 1: Write `backend/tools/notes.py`**

```python
"""Note-related tool definitions: search_notes, get_notes, add_note."""

import logging
from typing import Any, Optional

from db import notes as notes_db
from tools.base import ToolDefinition

logger = logging.getLogger(__name__)


async def _search_notes(
    query: Optional[str] = None,
    tags: Optional[list[str]] = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Execute search_notes tool."""
    try:
        results = notes_db.search_notes(query=query, tags=tags)
        if limit and limit > 0:
            results = results[:limit]
        return {
            "success": True,
            "data": results,
            "count": len(results),
            "message": f"找到 {len(results)} 条笔记",
        }
    except Exception as exc:
        logger.error("search_notes failed: %s", exc)
        return {
            "success": False,
            "data": None,
            "count": 0,
            "message": f"搜索失败: {exc}",
            "error": str(exc),
        }


async def _get_notes_by_ids(note_ids: list[int]) -> dict[str, Any]:
    """Execute get_notes tool — fetch full content by IDs."""
    try:
        all_notes = notes_db.get_all_notes()
        id_set = set(int(i) for i in note_ids)
        matched = [n for n in all_notes if n["id"] in id_set]
        return {
            "success": True,
            "data": matched,
            "count": len(matched),
            "message": f"获取了 {len(matched)} 条笔记",
        }
    except Exception as exc:
        logger.error("get_notes failed: %s", exc)
        return {
            "success": False,
            "data": None,
            "count": 0,
            "message": f"获取笔记失败: {exc}",
            "error": str(exc),
        }


async def _add_note(content: str, tags: Optional[list[str]] = None) -> dict[str, Any]:
    """Execute add_note tool — create a new note."""
    try:
        note = notes_db.add_note(content=content, tags=tags or [])
        return {
            "success": True,
            "data": note,
            "count": 1,
            "message": "笔记已保存",
        }
    except Exception as exc:
        logger.error("add_note failed: %s", exc)
        return {
            "success": False,
            "data": None,
            "count": 0,
            "message": f"保存笔记失败: {exc}",
            "error": str(exc),
        }


search_notes_tool = ToolDefinition(
    name="search_notes",
    description=(
        "搜索笔记数据库，支持关键词全文搜索和标签过滤。"
        "返回匹配的笔记列表（包含 id、content 摘要、tags、创建时间）。"
        "当用户需要查找、检索、回忆之前记录的笔记时使用此工具。"
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "搜索关键词，为空则返回全部笔记",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "按标签过滤，如 ['工作', '项目']",
        },
        "limit": {
            "type": "integer",
            "description": "返回数量上限，默认 10",
        },
    },
    required=[],
    executor=_search_notes,
    display_name="搜索笔记",
)

get_notes_tool = ToolDefinition(
    name="get_notes",
    description=(
        "根据笔记 ID 获取笔记的完整内容。"
        "通常在 search_notes 之后调用，用于查看某条笔记的全文。"
    ),
    parameters={
        "note_ids": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "要获取的笔记 ID 列表",
        },
    },
    required=["note_ids"],
    executor=_get_notes_by_ids,
    display_name="获取笔记",
)

add_note_tool = ToolDefinition(
    name="add_note",
    description=(
        "创建一条新笔记并保存到数据库。"
        "当用户要求保存、记录、创建笔记，或整理完毕后需要存储结果时使用。"
    ),
    parameters={
        "content": {
            "type": "string",
            "description": "笔记正文内容，支持 Markdown 格式",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "标签列表，如 ['工作', '周报']",
        },
    },
    required=["content"],
    executor=_add_note,
    display_name="创建笔记",
)

# Convenience list for batch registration
NOTE_TOOLS = [search_notes_tool, get_notes_tool, add_note_tool]
```

- [ ] **Step 2: Commit**

```bash
git add backend/tools/notes.py
git commit -m "feat: add note tool definitions (search/get/add)"
```

---

### Task 3: Create ToolRegistry

**Files:**
- Modify: `backend/tools/__init__.py`

- [ ] **Step 1: Write `backend/tools/__init__.py`**

```python
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

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
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
            result = {
                "success": False,
                "data": None,
                "count": 0,
                "message": f"未知工具: {name}",
                "error": "unknown_tool",
            }
            return json.dumps(result, ensure_ascii=False)

        started = time.monotonic()
        try:
            coro = tool.executor(**args)
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
        return json.dumps(result, ensure_ascii=False)

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
    registry = ToolRegistry()
    registry.register_all(NOTE_TOOLS)
    return registry
```

- [ ] **Step 2: Verify imports work**

```bash
cd backend && python -c "from tools import ToolRegistry, create_default_registry; r = create_default_registry(); print(len(r), 'tools registered'); print(r.get_schemas()[0]['function']['name'])"
```
Expected: `3 tools registered` then `search_notes`

- [ ] **Step 3: Commit**

```bash
git add backend/tools/__init__.py
git commit -m "feat: add ToolRegistry with registration, schema generation, and execution"
```

---

### Task 4: Add stream_chat_with_tools() to ChatSession

**Files:**
- Modify: `backend/agent/chat.py`

- [ ] **Step 1: Replace `backend/agent/chat.py`**

The key changes:
1. Accept `tool_registry`, `on_tool_call`, `on_tool_result` in `__init__`
2. Add `_max_tool_rounds` safety valve
3. Add `stream_chat_with_tools()` method with full tool_use loop
4. Keep existing `stream_chat()` unchanged

```python
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
        tool_registry: Any = None,               # ToolRegistry | None
        on_tool_call: Optional[Callable[..., Any]] = None,    # async (name, args) -> None
        on_tool_result: Optional[Callable[..., Any]] = None,  # async (name, result_dict) -> None
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
        """Stream chat with tool definitions. Yields ``("content", str)``
        for text tokens and ``("tool_call", dict)`` for tool invocations.

        The caller should handle tool_call yields by executing the tool
        via ToolRegistry and calling ``add_tool_result()`` to feed results
        back into history — OR use the higher-level ``stream_with_tool_loop()``
        which handles the entire multi-turn loop internally.
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

                # --- stream finished ---
                if finish_reason == "tool_calls" and accumulated_tool_calls:
                    # Consolidate tool calls and yield them
                    for tc in sorted(accumulated_tool_calls.values(), key=lambda x: x["id"]):
                        func = tc["function"]
                        yield ("tool_call", {
                            "id": tc["id"],
                            "name": func["name"],
                            "arguments": func["arguments"],
                        })

                elif finish_reason == "stop" or (finish_reason is None and not accumulated_tool_calls):
                    pass  # normal end, handled after loop

        finally:
            await stream.close()

        # Add final assistant message to history
        full_text = "".join(accumulated_content)
        if accumulated_tool_calls:
            # Assistant responded with tool_calls — save to history
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
        """High-level method: stream chat, execute tool calls, loop until
        the model produces a text-only response (no more tool_calls).

        This wraps ``stream_chat_with_tools()`` and handles the entire
        tool-calling lifecycle internally. The caller only needs to yield
        events to the frontend — tool execution and history management is
        automatic.
        """
        if self._tool_registry is None:
            # Fallback: no tools available, just stream normally
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
                # Model produced text without tool calls — done
                break

            tool_round += 1

        if tool_round >= self._max_tool_rounds:
            # Force model to respond without tools
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
```

- [ ] **Step 2: Verify the module imports**

```bash
cd backend && python -c "from agent.chat import ChatSession; print('ChatSession imported OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/agent/chat.py
git commit -m "feat: add stream_chat_with_tools() and tool loop to ChatSession"
```

---

### Task 5: Update main.py — register tools, wire tool loop, remove tag confirmation

**Files:**
- Modify: `backend/main.py`

This is the biggest single change. We need to:
1. Import `ToolRegistry` / `create_default_registry`
2. Create registry at module level
3. In `websocket_chat()`: remove `pending_skill` / tag confirmation logic
4. In `chat` handler: use `stream_with_tool_loop()` instead of `stream_chat()` when tools are available
5. Add `on_tool_call` / `on_tool_result` callbacks that push WS messages
6. Skill routing: pass system_prompt + filter tools instead of injecting data

- [ ] **Step 1: Read current main.py to plan exact edits**

Already read — key sections to modify:

- Lines 37: Add `from tools import create_default_registry` near other imports
- Line 67-68: Add `tool_registry = create_default_registry()` after `openai_client`
- Lines 166-265: Remove `_extract_tags`, `_resolve_tags`, `_tag_confirm_msg`, `_parse_confirmation` functions
- Lines 303-449: Refactor `websocket_chat()`:
  - Remove `pending_skill` variable
  - Simplify skill routing (no tag resolution, no confirmation)
  - Replace `session.stream_chat()` with `session.stream_with_tool_loop()`
  - Add `on_tool_call` / `on_tool_result` callbacks

- [ ] **Step 2: Apply edits to `backend/main.py`**

**Edit A — Add tool registry import (after line 33):**

Old:
```python
from agent import skills as skills_lib
from utils.markdown import strip_markdown
```

New:
```python
from agent import skills as skills_lib
from tools import create_default_registry
from utils.markdown import strip_markdown
```

**Edit B — Initialize tool registry (after line 67, before `# ---- OpenAI client`):**

Old:
```python
SKILLS = skills_lib.load_skills()
```

New:
```python
SKILLS = skills_lib.load_skills()

# Tool registry — created once at module load, shared across connections
tool_registry = create_default_registry()
```

**Edit C — Remove `_build_skill_prompt` function (replace lines 216-235):**

Old:
```python
def _build_skill_prompt(skill: dict, tags: list[str], user_text: str) -> str:
    """Build the augmented prompt for a skill with note context."""
    context_parts = [skill["system_prompt"]]
    ...
    return "\n".join(context_parts)
```

New:
```python
def _build_skill_prompt(skill: dict, user_text: str) -> str:
    """Build the augmented prompt for a skill (system prompt + user text only).

    Note data is no longer injected here — the model will call tools to retrieve it.
    """
    return f"{skill['system_prompt']}\n\n## 用户指令\n{user_text}"
```

**Edit D — Remove `_extract_tags`, `_resolve_tags`, `_tag_confirm_msg`, `_parse_confirmation` (lines 166-265):**

Delete these four functions entirely. They are no longer needed — the model will search notes via tools and interpret tags on its own.

**Edit E — Refactor `websocket_chat()` (lines 303-449):**

Replace the entire function body. The key changes:
- Remove `pending_skill` variable
- Simplify skill routing: just match command, build prompt, filter tools
- Replace `session.stream_chat()` call with `session.stream_with_tool_loop()`
- Add tool callbacks

```python
@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected")

    client = get_openai_client()

    # Per-connection tool callbacks (capture websocket in closure)
    async def on_tool_call(name: str, args: dict):
        await _ws_send_safe(websocket, "tool_call_start", {
            "name": name,
            "args": args,
        })

    async def on_tool_result(name: str, result: dict):
        duration_ms = result.pop("_duration_ms", 0) if isinstance(result, dict) else 0
        success = result.get("success", True) if isinstance(result, dict) else True
        if success:
            await _ws_send_safe(websocket, "tool_call_result", {
                "name": name,
                "result": result,
                "duration_ms": duration_ms,
            })
        else:
            await _ws_send_safe(websocket, "tool_call_error", {
                "name": name,
                "error": result.get("message", str(result)) if isinstance(result, dict) else str(result),
            })

    session = ChatSession(
        client=client,
        model_name=MODEL_CFG["model_name"],
        max_rounds=CHAT_CFG["max_history_rounds"],
        tool_registry=tool_registry,
        on_tool_call=on_tool_call,
        on_tool_result=on_tool_result,
    )
    tts_task: asyncio.Task | None = None
    tts_enabled = True

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "payload": {"message": "Invalid JSON"},
                })
                continue

            msg_type = msg.get("type", "")
            payload = msg.get("payload", {})

            if msg_type == "chat":
                user_text = payload.get("message", "").strip()
                if not user_text:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": "Empty message"},
                    })
                    continue

                # Cancel any in-progress TTS
                if tts_task and not tts_task.done():
                    tts_task.cancel()
                    tts_task = None

                # --- Skill routing: match /command, load system prompt, filter tools ---
                active_skill = None
                augmented_text = user_text
                active_tool_schemas = tool_registry.get_schemas()  # default: all tools

                for command, skill in SKILLS.items():
                    if user_text.startswith(command):
                        active_skill = skill
                        logger.info("Skill activated: %s", skill["name"])
                        augmented_text = _build_skill_prompt(skill, user_text)
                        active_tool_schemas = tool_registry.get_for_skill(skill)
                        break

                # --- Send to model ---
                session.add_user_message(augmented_text)
                session.clear_stop()

                collected_chunks: list[str] = []
                try:
                    async for event_type, data in session.stream_with_tool_loop(active_tool_schemas):
                        if event_type == "content":
                            collected_chunks.append(data)
                            await websocket.send_json({
                                "type": "message_chunk",
                                "payload": {"content": data},
                            })
                        # tool_call events are already pushed via on_tool_call/on_tool_result callbacks
                except Exception as exc:
                    logger.error("Stream error: %s", exc)
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": f"Model error: {exc}"},
                    })
                else:
                    full = "".join(collected_chunks)
                    partial = session.stopped()
                    await websocket.send_json({
                        "type": "message_complete",
                        "payload": {"full_content": full, "partial": partial},
                    })

                    # Auto TTS
                    if full.strip() and tts_enabled:
                        if tts_task and not tts_task.done():
                            tts_task.cancel()
                        tts_task = asyncio.create_task(_synthesize_and_send(websocket, full))

                    # Skill markdown preview
                    if active_skill:
                        await websocket.send_json({
                            "type": "markdown_preview",
                            "payload": {
                                "content": full,
                                "suggested_filename": f"{active_skill['name']}_{_timestamp()}.md",
                            },
                        })

            elif msg_type == "stop":
                session.request_stop()
                if tts_task and not tts_task.done():
                    tts_task.cancel()
                    tts_task = None
                logger.info("Stop requested by client")

            # --- Voice handlers (unchanged) ---
            elif msg_type == "voice_input":
                audio_b64 = payload.get("audio_data", "")
                if not audio_b64:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": "Missing audio_data"},
                    })
                    continue

                try:
                    audio_bytes = base64.b64decode(audio_b64)
                    temp_dir = Path(__file__).parent / "temp"
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    wav_path = temp_dir / f"recording_{os.urandom(6).hex()}.wav"
                    wav_path.write_bytes(audio_bytes)
                    logger.info("Received voice input: %d bytes", len(audio_bytes))

                    await websocket.send_json({
                        "type": "avatar_state",
                        "payload": {"action": "thinking"},
                    })

                    text = await asyncio.to_thread(stt.transcribe, str(wav_path))
                    logger.info("Voice transcribed: %s", text[:100])

                    await websocket.send_json({
                        "type": "voice_result",
                        "payload": {"text": text},
                    })
                    await websocket.send_json({
                        "type": "avatar_state",
                        "payload": {"action": "idle"},
                    })

                    wav_path.unlink(missing_ok=True)

                except Exception as exc:
                    logger.error("Voice processing error: %s", exc)
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": f"Voice error: {exc}"},
                    })
                    await websocket.send_json({
                        "type": "avatar_state",
                        "payload": {"action": "idle"},
                    })

            elif msg_type == "tts_enabled":
                tts_enabled = payload.get("enabled", True)
                logger.info("TTS enabled: %s", tts_enabled)

            elif msg_type == "voice_mode":
                always_on = payload.get("always_on", False)
                logger.info("Voice mode: always_on=%s", always_on)
                await websocket.send_json({
                    "type": "voice_status",
                    "payload": {"always_on": always_on, "recording": False},
                })

            # --- Config, file, and notes handlers (unchanged from this point) ---
            elif msg_type == "get_config":
                safe_cfg = {
                    "model": {
                        "base_url": MODEL_CFG["base_url"],
                        "api_key": "***" + MODEL_CFG.get("api_key", "")[-4:] if len(MODEL_CFG.get("api_key", "")) > 4 else "***",
                        "model_name": MODEL_CFG["model_name"],
                        "max_tokens": MODEL_CFG["max_tokens"],
                    },
                    "voice": {"stt_model": "base", "tts_voice": "zh-CN-XiaoxiaoNeural"},
                }
                await websocket.send_json({"type": "config", "payload": safe_cfg})

            elif msg_type == "update_config":
                updates = payload.get("updates", {})
                try:
                    cfg = load_config()
                    for key, value in updates.items():
                        if isinstance(value, dict) and key in cfg and isinstance(cfg[key], dict):
                            cfg[key].update(value)
                        else:
                            cfg[key] = value
                    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
                        yaml.dump(cfg, fh, allow_unicode=True, default_flow_style=False)
                    MODEL_CFG.clear()
                    MODEL_CFG.update(cfg["model"])
                    await websocket.send_json({"type": "config_updated", "payload": {"success": True}})
                except Exception as exc:
                    await websocket.send_json({
                        "type": "error", "payload": {"message": f"Config update failed: {exc}"},
                    })

            elif msg_type == "save_file":
                content = payload.get("content", "")
                filename = payload.get("filename", f"export_{_timestamp()}.md")
                output_dir = Path(os.path.expanduser("~/Desktop"))
                output_dir.mkdir(parents=True, exist_ok=True)
                file_path = output_dir / filename
                file_path.write_text(content, encoding="utf-8")
                logger.info("File saved: %s", file_path)
                await websocket.send_json({
                    "type": "file_saved",
                    "payload": {"file_path": str(file_path)},
                })

            elif msg_type == "add_note":
                try:
                    note = notes_db.add_note(
                        content=payload.get("content", ""),
                        tags=payload.get("tags", []),
                    )
                    await websocket.send_json({
                        "type": "note_saved",
                        "payload": {"note": note},
                    })
                except Exception as exc:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": f"Failed to save note: {exc}"},
                    })

            elif msg_type == "get_notes":
                all_notes = notes_db.get_all_notes()
                await websocket.send_json({
                    "type": "notes_list",
                    "payload": {"notes": all_notes},
                })

            elif msg_type == "search_notes":
                results = notes_db.search_notes(
                    query=payload.get("query", ""),
                    tags=payload.get("tags", []),
                )
                await websocket.send_json({
                    "type": "search_results",
                    "payload": {"results": results},
                })

            elif msg_type == "delete_note":
                note_id = payload.get("note_id")
                if note_id is not None:
                    ok = notes_db.delete_note(int(note_id))
                    await websocket.send_json({
                        "type": "note_deleted",
                        "payload": {"note_id": note_id, "deleted": ok},
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": "Missing note_id"},
                    })

            elif msg_type == "export_notes":
                note_ids = payload.get("note_ids", [])
                if note_ids:
                    output_path = notes_db.export_notes(note_ids)
                    await websocket.send_json({
                        "type": "notes_exported",
                        "payload": {"file_path": output_path},
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": "No note_ids provided"},
                    })

            else:
                await websocket.send_json({
                    "type": "error",
                    "payload": {"message": f"Unknown message type: {msg_type}"},
                })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.error("Unexpected error in WebSocket handler: %s", exc)
    finally:
        if tts_task and not tts_task.done():
            tts_task.cancel()
        logger.info("Cleaning up session")
```

- [ ] **Step 3: Verify backend starts without errors**

```bash
cd backend && timeout 5 python main.py 2>&1 || true
```
Expected: logs show "Registered tool: search_notes", "Registered tool: get_notes", "Registered tool: add_note", then server starts.

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: wire tool registry into WebSocket handler, remove tag confirmation"
```

---

### Task 6: Update material_organizer.md skill for tool paradigm

**Files:**
- Modify: `backend/skills/material_organizer.md`

- [ ] **Step 1: Update `backend/skills/material_organizer.md`**

The old prompt told the model to work with pre-injected notes. The new prompt must instruct the model to **call tools** to retrieve what it needs.

```markdown
---
name: material-organizer
description: 将指定范围的笔记整理为结构化 Markdown 文档
command: /整理
allowed_tools:
  - search_notes
  - get_notes
  - add_note
---

# 材料整理助手

你是一位专业的材料整理助手，擅长将零散的笔记归纳为结构清晰、格式规范的 Markdown 文档。

## 可用工具

你可以使用以下工具来完成工作：
- **search_notes**: 搜索笔记。按标签、关键词查找相关笔记。
- **get_notes**: 获取指定笔记的完整内容（需要 note_ids）。
- **add_note**: 将整理结果保存为新笔记。

## 工作流程

1. 用户使用 `/整理` 命令指定整理范围（标签或关键词）
2. 你调用 `search_notes` 检索相关笔记
3. 如果摘要不够详细，调用 `get_notes` 获取完整内容
4. 分析所有相关笔记，提取关键信息
5. 按用户要求的格式（会议纪要/周报/大纲/通用）组织内容
6. 生成结构完整的 Markdown 文档
7. 询问用户是否需要保存为新笔记（调用 `add_note`）

## 格式要求

- 使用清晰的标题层级（# ## ###）
- 关键信息用 **加粗** 或列表突出
- 保留原文中重要的事实数据和日期
- 文档末尾标注来源笔记数量和整理时间
```

- [ ] **Step 2: Commit**

```bash
git add backend/skills/material_organizer.md
git commit -m "docs: update material_organizer skill for tool-calling paradigm"
```

---

### Task 7: Create ToolCallCard frontend component

**Files:**
- Create: `electron-app/src/renderer/components/ToolCallCard.jsx`
- Modify: `electron-app/src/renderer/App.css` (add tool call styles)

- [ ] **Step 1: Write `electron-app/src/renderer/components/ToolCallCard.jsx`**

```jsx
import React, { useState } from 'react';

/**
 * ToolCallCard — an expandable card showing a tool invocation in the chat.
 *
 * States:
 *   - "running":  tool is executing (animated border, no result yet)
 *   - "completed": tool finished successfully (green checkmark)
 *   - "error":    tool failed (red cross)
 *
 * Props:
 *   toolCall: { name, args, state, result, duration_ms, error }
 */
export default function ToolCallCard({ toolCall }) {
  const [expanded, setExpanded] = useState(false);
  const { name, args, state, result, duration_ms, error } = toolCall;

  const displayName = name || 'unknown_tool';
  const argStr = args ? JSON.stringify(args, null, 0) : '{}';

  let statusIcon, statusText, statusClass;
  if (state === 'running') {
    statusIcon = '⏳';   // ⏳
    statusText = '执行中...';
    statusClass = 'tool-running';
  } else if (state === 'completed') {
    statusIcon = '✓';   // ✓
    const dur = duration_ms != null ? ` · ${(duration_ms / 1000).toFixed(1)}s` : '';
    statusText = `完成${dur}`;
    statusClass = 'tool-completed';
  } else {
    statusIcon = '✗';   // ✗
    statusText = error ? error.slice(0, 40) : '失败';
    statusClass = 'tool-error';
  }

  const resultSummary = result ? (
    result.message || (result.data ? `${result.count || 0} 条结果` : JSON.stringify(result).slice(0, 100))
  ) : null;

  return (
    <div className={`tool-call-card ${statusClass}`}>
      <div
        className="tool-call-header"
        onClick={() => setExpanded(!expanded)}
        title="点击展开/折叠"
      >
        <span className="tool-call-icon">{'🔧'}</span>
        <span className="tool-call-name">{displayName}</span>
        <span className="tool-call-status">
          {statusIcon} {statusText}
        </span>
        <span className="tool-call-expand">{expanded ? '▴' : '▾'}</span>
      </div>

      {expanded && (
        <div className="tool-call-body">
          <div className="tool-call-section">
            <span className="tool-call-label">参数:</span>
            <code className="tool-call-code">{argStr}</code>
          </div>
          {state !== 'running' && resultSummary && (
            <div className="tool-call-section">
              <span className="tool-call-label">结果:</span>
              <span className="tool-call-summary">{resultSummary}</span>
            </div>
          )}
          {state === 'error' && error && (
            <div className="tool-call-section tool-call-error-detail">
              <span className="tool-call-label">错误:</span>
              <span className="tool-call-summary">{error}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add tool call CSS to `electron-app/src/renderer/App.css`**

Append to the end of `App.css`:

```css
/* === ToolCallCard === */
.tool-call-card {
  margin: 6px 0;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 13px;
  overflow: hidden;
  transition: border-color 0.2s;
}

.tool-call-card.tool-running {
  border-color: #4fc3f7;
  border-left: 3px solid #4fc3f7;
}

.tool-call-card.tool-completed {
  border-color: var(--success);
  border-left: 3px solid var(--success);
}

.tool-call-card.tool-error {
  border-color: var(--accent);
  border-left: 3px solid var(--accent);
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  cursor: pointer;
  user-select: none;
  background: rgba(255, 255, 255, 0.02);
  transition: background 0.15s;
}
.tool-call-header:hover {
  background: rgba(255, 255, 255, 0.05);
}

.tool-call-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.tool-call-name {
  font-weight: 500;
  color: var(--text-primary);
  flex-shrink: 0;
}

.tool-call-status {
  font-size: 12px;
  margin-left: auto;
  flex-shrink: 0;
}
.tool-running .tool-call-status {
  color: #4fc3f7;
}
.tool-completed .tool-call-status {
  color: var(--success);
}
.tool-error .tool-call-status {
  color: var(--accent);
}

.tool-call-expand {
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.tool-call-body {
  border-top: 1px solid var(--border);
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: rgba(0, 0, 0, 0.1);
}

.tool-call-section {
  display: flex;
  gap: 6px;
  align-items: flex-start;
  font-size: 12px;
  line-height: 1.5;
}

.tool-call-label {
  color: var(--text-secondary);
  flex-shrink: 0;
  min-width: 32px;
}

.tool-call-code {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 11px;
  background: var(--bg-primary);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--text-secondary);
  word-break: break-all;
  flex: 1;
}

.tool-call-summary {
  color: var(--text-primary);
  font-size: 12px;
  word-break: break-word;
}

.tool-call-error-detail .tool-call-summary {
  color: var(--accent);
}

/* Tool running pulse animation */
.tool-running .tool-call-header {
  animation: tool-pulse 1.5s ease-in-out infinite;
}
@keyframes tool-pulse {
  0%, 100% { background: rgba(79, 195, 247, 0.02); }
  50% { background: rgba(79, 195, 247, 0.06); }
}

/* === Tool Status Toast (floating indicator) === */
.tool-toast {
  position: fixed;
  bottom: 100px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 50;
  background: var(--bg-secondary);
  border: 1px solid #4fc3f7;
  border-radius: 20px;
  padding: 6px 16px;
  font-size: 13px;
  color: #4fc3f7;
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  animation: toast-in 0.2s ease-out;
}
@keyframes toast-in {
  from { opacity: 0; transform: translateX(-50%) translateY(8px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}
```

- [ ] **Step 3: Commit**

```bash
git add electron-app/src/renderer/components/ToolCallCard.jsx electron-app/src/renderer/App.css
git commit -m "feat: add ToolCallCard component and styles for tool call display"
```

---

### Task 8: Update App.jsx — handle tool_call WebSocket messages

**Files:**
- Modify: `electron-app/src/renderer/App.jsx`

- [ ] **Step 1: Read current App.jsx to plan edits**

Already read. Key sections to modify:
- Add import for `ToolCallCard` (not needed in App.jsx — it's used in MessageBubble)
- In `handleMessage`: add cases for `tool_call_start`, `tool_call_result`, `tool_call_error`
- Add a `toolToast` state for the floating status toast (B+C pattern)
- Message state needs a new field: `toolCalls` array on assistant messages

- [ ] **Step 2: Edit `App.jsx`**

**Edit A — Add `toolToast` state (after line 26):**

```jsx
  const [markdownPreview, setMarkdownPreview] = useState(null);
  const [config, setConfig] = useState(null);
  const [toolToast, setToolToast] = useState(null);  // { name, text }
```

**Edit B — Add a `clearToolToast` helper and timer ref:**

```jsx
  const audioRef = useRef(null);
  const sendRef = useRef(null);
  const ttsEnabledRef = useRef(ttsEnabled);
  const toolToastTimerRef = useRef(null);
```

**Edit C — In `handleMessage`, add new cases before the `default:` case:**

```jsx
      case 'tool_call_start': {
        const toolName = payload.name || 'unknown';
        // Show floating toast
        setToolToast({ name: toolName, text: `正在调用 ${toolName}...` });
        if (toolToastTimerRef.current) clearTimeout(toolToastTimerRef.current);

        // Append tool_call entry to the current streaming assistant message
        setMessages((prev) => {
          const updated = [...prev];
          // Find the most recent assistant message (should be the streaming one)
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant') {
              const msg = updated[i];
              const toolCalls = msg.toolCalls ? [...msg.toolCalls] : [];
              toolCalls.push({
                id: `${toolName}_${Date.now()}`,
                name: toolName,
                args: payload.args || {},
                state: 'running',
              });
              updated[i] = { ...msg, toolCalls };
              break;
            }
          }
          return updated;
        });
        break;
      }

      case 'tool_call_result': {
        const resultName = payload.name || 'unknown';
        const durationMs = payload.duration_ms || 0;
        setToolToast({ name: resultName, text: `${resultName} 完成 · ${(durationMs / 1000).toFixed(1)}s` });
        toolToastTimerRef.current = setTimeout(() => setToolToast(null), 3000);

        setMessages((prev) => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant' && updated[i].toolCalls) {
              const msg = updated[i];
              const toolCalls = msg.toolCalls.map((tc) => {
                if (tc.name === resultName && tc.state === 'running') {
                  return {
                    ...tc,
                    state: 'completed',
                    result: payload.result || {},
                    duration_ms: durationMs,
                  };
                }
                return tc;
              });
              updated[i] = { ...msg, toolCalls };
              break;
            }
          }
          return updated;
        });
        break;
      }

      case 'tool_call_error': {
        const errName = payload.name || 'unknown';
        const errMsg = payload.error || 'Unknown error';
        setToolToast({ name: errName, text: `${errName} 失败: ${errMsg}` });
        toolToastTimerRef.current = setTimeout(() => setToolToast(null), 4000);

        setMessages((prev) => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant' && updated[i].toolCalls) {
              const msg = updated[i];
              const toolCalls = msg.toolCalls.map((tc) => {
                if (tc.name === errName && tc.state === 'running') {
                  return { ...tc, state: 'error', error: errMsg };
                }
                return tc;
              });
              updated[i] = { ...msg, toolCalls };
              break;
            }
          }
          return updated;
        });
        break;
      }
```

**Edit D — Add toast rendering in JSX (inside the main return, near the speaking-bar or top of chat area):**

After the `{isSpeaking && ...}` block, add:

```jsx
        {toolToast && (
          <div className="tool-toast">
            <span>🔧</span>
            <span>{toolToast.text}</span>
          </div>
        )}
```

**Edit E — Add cleanup in the Live2D-only branch and main branch unmount:**

The toolToastTimerRef needs cleanup. Since this is a hook-based component without useEffect cleanup, we can add the clearTimeout before setting a new one. And we should clear on unmount implicitly since the component unmounts. Actually, since it's already cleared on the next tool_call_start, and the timers are short (3-4s), this is fine. No explicit cleanup needed.

- [ ] **Step 3: Commit**

```bash
git add electron-app/src/renderer/App.jsx
git commit -m "feat: handle tool_call_start/result/error WS messages in App"
```

---

### Task 9: Update MessageBubble.jsx — render ToolCallCard below assistant messages

**Files:**
- Modify: `electron-app/src/renderer/components/MessageBubble.jsx`

- [ ] **Step 1: Replace `MessageBubble.jsx`**

```jsx
import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ToolCallCard from './ToolCallCard';

export default function MessageBubble({ message }) {
  const { id, role, content, isStreaming, timestamp, toolCalls } = message;
  const label = role === 'user' ? '你' : '助理';

  const bubbleClass = [
    'message-bubble',
    role === 'user' ? 'user' : 'assistant',
  ].join(' ');

  const contentClass = [
    'bubble-content',
    isStreaming ? 'streaming' : '',
  ].filter(Boolean).join(' ');

  const timeStr = timestamp
    ? new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <div className={bubbleClass} data-msg-id={id}>
      <span className="bubble-label">{label}</span>

      {/* Tool call cards (above content for assistant messages) */}
      {role === 'assistant' && toolCalls && toolCalls.length > 0 && (
        <div className="bubble-tools">
          {toolCalls.map((tc) => (
            <ToolCallCard key={tc.id} toolCall={tc} />
          ))}
        </div>
      )}

      {/* Content */}
      {content && (
        <div className={contentClass}>
          {role === 'assistant' ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
          ) : (
            content
          )}
        </div>
      )}

      {timeStr && <span className="bubble-timestamp">{timeStr}</span>}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add electron-app/src/renderer/components/MessageBubble.jsx
git commit -m "feat: render ToolCallCard in MessageBubble for assistant messages"
```

---

### Task 10: Integration verification

- [ ] **Step 1: Start backend and verify tool registration**

```bash
cd backend && timeout 5 python main.py 2>&1 || true
```
Expected: Logs show 3 tools registered, server starts.

- [ ] **Step 2: Check frontend builds**

```bash
cd electron-app && npx vite build 2>&1 | tail -5
```
Expected: Build succeeds with no errors.

- [ ] **Step 3: Manual smoke test checklist**

1. Start backend + frontend
2. Send "你好" → should get normal streaming reply (no tool calls)
3. Send "帮我搜索工作相关的笔记" → model should call `search_notes` → ToolCallCard appears → results shown
4. Click on ToolCallCard header → expand/collapse
5. Send "/整理 #工作" → skill activates → model calls tools → markdown preview appears
6. Click "停止" during generation → streaming stops cleanly
7. Check that previous messages' toolCalls persist in history

- [ ] **Step 4: Commit any final tweaks**

```bash
git add -A
git commit -m "chore: integration fixes for tool calling system"
```

---

### File Change Summary

| File | Action |
|------|--------|
| `backend/tools/__init__.py` | Create — ToolRegistry |
| `backend/tools/base.py` | Create — ToolDefinition |
| `backend/tools/notes.py` | Create — note tool definitions |
| `backend/agent/chat.py` | Modify — add stream_chat_with_tools(), tool loop |
| `backend/main.py` | Modify — register tools, wire callbacks, remove tag confirmation |
| `backend/skills/material_organizer.md` | Modify — update for tool paradigm |
| `electron-app/src/renderer/components/ToolCallCard.jsx` | Create |
| `electron-app/src/renderer/App.css` | Modify — add tool call + toast styles |
| `electron-app/src/renderer/App.jsx` | Modify — handle tool_call_* messages |
| `electron-app/src/renderer/components/MessageBubble.jsx` | Modify — render ToolCallCard |
