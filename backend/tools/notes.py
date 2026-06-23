"""Note-related tool definitions for LLM function calling.

Public tools: search_notes, get_notes, add_note
Secret tool:  search_secret_notes (returns placeholders to LLM, pushes real
              results to frontend via WebSocket callback)
"""

import logging
from typing import Any, Optional

from db import notes as notes_db
from db import secret_notes as secret_notes_db
from security.guard import build_secret_placeholder
from tools.base import ToolDefinition

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------

async def _search_notes(
    query: Optional[str] = None,
    tags: Optional[list[str]] = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Execute search_notes tool against public knowledge_items."""
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
    """Execute get_notes tool — fetch full public notes by IDs."""
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
    """Execute add_note tool — create a new public note."""
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


# ---------------------------------------------------------------------------
# Secret tool — search_secret_notes
# ---------------------------------------------------------------------------

async def _search_secret_notes(
    query: Optional[str] = None,
    tags: Optional[list[str]] = None,
    limit: int = 10,
    _ws_sender: Optional[Any] = None,  # injected by ToolRegistry.execute()
) -> dict[str, Any]:
    """Execute search_secret_notes tool.

    CRITICAL SECURITY BEHAVIOR:
      1. Queries the real secret database.
      2. Pushes real results to the frontend via WebSocket callback (if set).
      3. Returns a sanitized PLACEHOLDER to the LLM — real data NEVER enters
         the LLM's context or the OpenAI HTTP request body.
    """
    try:
        results = secret_notes_db.search_secret_notes(query=query, tags=tags)
        if limit and limit > 0:
            results = results[:limit]

        # Push real results to frontend (bypasses LLM)
        if _ws_sender is not None:
            try:
                await _ws_sender("secret_search_results", {
                    "results": results,
                    "count": len(results),
                    "query": query or "",
                })
            except Exception as exc:
                logger.error("Failed to push secret results to frontend: %s", exc)

        # Return sanitized placeholder to LLM — NO REAL DATA
        return build_secret_placeholder(len(results), query or "")

    except Exception as exc:
        logger.error("search_secret_notes failed: %s", exc)
        return {
            "success": False,
            "data": None,
            "count": 0,
            "message": f"搜索秘密笔记失败: {exc}",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

search_notes_tool = ToolDefinition(
    name="search_notes",
    description=(
        "搜索公开笔记数据库。同时搜索笔记标题和正文内容（关键词）和标签名。"
        "返回匹配的笔记列表（包含 id、content 摘要、tags、创建时间）。"
        "当用户需要查找、检索、回忆之前记录的笔记时使用此工具。"
        "**重要**：如果用户提到了类别、主题、领域（如'编程语言''工作''项目'），"
        "优先使用 tags 参数过滤，而不是 query。"
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "搜索笔记标题和正文的关键词。如果用户明确说的是标签名/类别，请用 tags 参数代替。",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "按标签名精确过滤。用户提到的分类/类别/主题都应作为 tags。如用户说'编程语言的笔记'则应传 ['编程语言']",
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
        "根据笔记 ID 获取公开笔记的完整内容。"
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
        "创建一条新笔记并保存到公开数据库。"
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

search_secret_notes_tool = ToolDefinition(
    name="search_secret_notes",
    description=(
        "搜索用户的秘密笔记数据库（隐私空间）。按关键词或标签搜索。"
        "**重要安全规则**：此工具返回脱敏结果（仅数量），真实秘密内容直接推送至"
        "前端安全面板，绝对不会出现在你的对话上下文中。"
        "你必须在回复中告知用户'已检索到 N 条秘密记录，详情请查看安全面板 🔒'，"
        "**绝对不要**编造或猜测秘密笔记的具体内容。"
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "搜索秘密笔记标题和正文的关键词",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "按标签名精确过滤",
        },
        "limit": {
            "type": "integer",
            "description": "返回数量上限，默认 10",
        },
    },
    required=[],
    executor=_search_secret_notes,
    display_name="搜索秘密笔记",
)

# Convenience lists for batch registration
PUBLIC_NOTE_TOOLS = [search_notes_tool, get_notes_tool, add_note_tool]
SECRET_NOTE_TOOLS = [search_secret_notes_tool]
NOTE_TOOLS = PUBLIC_NOTE_TOOLS + SECRET_NOTE_TOOLS
