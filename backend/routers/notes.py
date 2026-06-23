"""公开笔记 + 秘密笔记 WS 消息处理。"""

from fastapi import WebSocket

from db import notes as notes_db
from db import secret_notes as secret_notes_db
from security.guard import build_secret_placeholder


# ═══════════════════════════════════════════════════════════════════════
# 秘密笔记（独立处理，不经过 LLM）
# ═══════════════════════════════════════════════════════════════════════

async def handle_secret_message(websocket: WebSocket, msg_type: str, payload: dict) -> bool:
    """处理 secret_* 前缀消息。返回 True 表示已处理。"""
    try:
        if msg_type == "secret_add_note":
            note = secret_notes_db.add_secret_note(
                content=payload.get("content", ""),
                tags=payload.get("tags", []),
            )
            await _ws_send(websocket, "secret_note_saved", {"note": note})
            return True

        elif msg_type == "secret_get_notes":
            notes = secret_notes_db.get_all_secret_notes()
            await _ws_send(websocket, "secret_notes_list", {"notes": notes})
            return True

        elif msg_type == "secret_search_notes":
            results = secret_notes_db.search_secret_notes(
                query=payload.get("query", ""),
                tags=payload.get("tags", []),
            )
            # 仅推送前端；不给 LLM
            await _ws_send(websocket, "secret_search_results", {
                "results": results,
                "count": len(results),
                "query": payload.get("query", ""),
            })
            return True

        elif msg_type == "secret_delete_note":
            note_id = payload.get("note_id")
            if note_id is not None:
                ok = secret_notes_db.delete_secret_note(int(note_id))
                await _ws_send(websocket, "secret_note_deleted", {"note_id": note_id, "deleted": ok})
            return True

    except Exception as exc:
        await _ws_send(websocket, "error", {"message": f"Secret operation failed: {exc}"})
        return True

    return False


# ═══════════════════════════════════════════════════════════════════════
# 公开笔记
# ═══════════════════════════════════════════════════════════════════════

async def handle_public_notes(websocket: WebSocket, msg_type: str, payload: dict) -> bool:
    """处理公开笔记消息。返回 True 表示已处理。"""
    try:
        if msg_type == "add_note":
            note = notes_db.add_note(
                content=payload.get("content", ""),
                tags=payload.get("tags", []),
            )
            await _ws_send(websocket, "note_saved", {"note": note})
            return True

        elif msg_type == "get_notes":
            all_notes = notes_db.get_all_notes()
            await _ws_send(websocket, "notes_list", {"notes": all_notes})
            return True

        elif msg_type == "search_notes":
            results = notes_db.search_notes(
                query=payload.get("query", ""),
                tags=payload.get("tags", []),
            )
            await _ws_send(websocket, "search_results", {"results": results})
            return True

        elif msg_type == "delete_note":
            note_id = payload.get("note_id")
            if note_id is not None:
                ok = notes_db.delete_note(int(note_id))
                await _ws_send(websocket, "note_deleted", {"note_id": note_id, "deleted": ok})
            else:
                await _ws_send(websocket, "error", {"message": "Missing note_id"})
            return True

        elif msg_type == "export_notes":
            note_ids = payload.get("note_ids", [])
            if note_ids:
                output_path = notes_db.export_notes(note_ids)
                await _ws_send(websocket, "notes_exported", {"file_path": output_path})
            else:
                await _ws_send(websocket, "error", {"message": "No note_ids provided"})
            return True

    except Exception as exc:
        await _ws_send(websocket, "error", {"message": f"Note operation failed: {exc}"})
        return True

    return False


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

async def _ws_send(websocket: WebSocket, msg_type: str, payload: dict) -> None:
    """Safely send a JSON message over WebSocket."""
    try:
        await websocket.send_json({"type": msg_type, "payload": payload})
    except Exception:
        pass  # 连接已断开，忽略
