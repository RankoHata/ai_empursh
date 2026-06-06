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
        "搜索笔记数据库。同时搜索笔记正文（关键词）和标签名。"
        "返回匹配的笔记列表（包含 id、content 摘要、tags、创建时间）。"
        "当用户需要查找、检索、回忆之前记录的笔记时使用此工具。"
        "**重要**：如果用户提到了类别、主题、领域（如'编程语言''工作''项目'），"
        "优先使用 tags 参数过滤，而不是 query。"
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "搜索笔记正文的关键词。如果用户明确说的是标签名/类别，请用 tags 参数代替。",
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
