"""对话管理 WS 消息处理。"""

import logging
from typing import Any, Optional

from fastapi import WebSocket

from db import conversations as conv_db

logger = logging.getLogger(__name__)


async def handle_conversations(
    websocket: WebSocket,
    msg_type: str,
    payload: dict,
    session: Any,
    current_conv_id: Optional[str],
    turn_index: int,
) -> tuple[Optional[str], int]:
    """处理对话消息。返回 (new_conv_id, new_turn_index)。"""
    try:
        if msg_type == "delete_turn":
            t_idx = payload.get("turn_index")
            conv_id = payload.get("conversation_id", current_conv_id or "")
            if conv_id and t_idx is not None:
                deleted = conv_db.delete_turn(conv_id, int(t_idx))
                await _ws(websocket, "turn_deleted", {
                    "conversation_id": conv_id, "turn_index": t_idx, "deleted": deleted,
                })
            else:
                await _ws(websocket, "error", {"message": "Missing conversation_id or turn_index"})

        elif msg_type == "create_conversation":
            conv = conv_db.create_conversation(title=payload.get("title", "新对话"))
            await _ws(websocket, "conversation_created", conv)
            current_conv_id = conv["id"]
            turn_index = 0

        elif msg_type == "list_conversations":
            convs = conv_db.list_conversations()
            await _ws(websocket, "conversations_list", {"conversations": convs})

        elif msg_type == "delete_conversation":
            conv_id = payload.get("conversation_id", "")
            if conv_id:
                deleted = conv_db.delete_conversation(conv_id)
                if conv_id == current_conv_id:
                    current_conv_id = None
                    turn_index = 0
                    logger.info("Current conversation %s deleted, resetting", conv_id)
                await _ws(websocket, "conversation_deleted", {
                    "conversation_id": conv_id, "deleted": deleted,
                })

        elif msg_type == "rename_conversation":
            conv_id = payload.get("conversation_id", "")
            title = payload.get("title", "").strip()
            if conv_id and title:
                ok = conv_db.update_conversation_title(conv_id, title)
                await _ws(websocket, "conversation_renamed", {
                    "conversation_id": conv_id, "title": title, "ok": ok,
                })

        elif msg_type == "get_turns":
            conv_id = payload.get("conversation_id", current_conv_id or "")
            if conv_id:
                turns = conv_db.get_turns(conv_id)
                await _ws(websocket, "turns_list", {"turns": turns, "conversation_id": conv_id})

        elif msg_type == "load_conversation":
            conv_id = payload.get("conversation_id", "")
            if conv_id:
                conv = conv_db.get_conversation(conv_id)
                if conv:
                    messages = conv_db.build_history_from_turns(conv_id)
                    session.load_history(messages)
                    current_conv_id = conv_id
                    turn_index = conv_db.get_turn_count(conv_id)
                    logger.info("Loaded conversation %s: %d turns, %d messages",
                                conv_id, turn_index, len(messages))
                    await _ws(websocket, "conversation_loaded", {
                        "conversation": conv, "turn_count": turn_index,
                    })

    except Exception as exc:
        logger.error("Conversation handler error: %s", exc)
        await _ws(websocket, "error", {"message": f"Conversation operation failed: {exc}"})

    return current_conv_id, turn_index


def is_conversation_msg(msg_type: str) -> bool:
    """判断消息类型是否属于对话管理。"""
    return msg_type in (
        "delete_turn", "create_conversation", "list_conversations",
        "delete_conversation", "rename_conversation", "get_turns", "load_conversation",
    )


async def _ws(websocket: WebSocket, msg_type: str, payload: dict) -> None:
    try:
        await websocket.send_json({"type": msg_type, "payload": payload})
    except Exception:
        pass
