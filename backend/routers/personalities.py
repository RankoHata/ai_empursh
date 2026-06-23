"""人格管理 WS 消息处理。"""

from typing import Any

from fastapi import WebSocket


async def handle_personalities(
    websocket: WebSocket,
    msg_type: str,
    payload: dict,
    manager: Any,
    current_personality: dict | None,
) -> dict | None:
    """处理人格相关消息。返回更新后的 current_personality（若变更）。"""
    try:
        if msg_type == "get_personalities":
            plist = manager.list_all()
            grouped = manager.list_grouped()
            await _ws_send(websocket, "personalities_list", {
                "personalities": plist,
                "grouped": grouped,
                "current": current_personality.get("id") if current_personality else None,
            })

        elif msg_type == "set_personality":
            pid = int(payload.get("personality_id", 0))
            p = manager.get(pid)
            if p:
                current_personality = p
                await _ws_send(websocket, "personality_set", {"id": pid})

        elif msg_type == "create_personality":
            p = manager.create(
                name=payload.get("name", ""),
                description=payload.get("description", ""),
                system_prompt=payload.get("system_prompt", ""),
                parent_id=payload.get("parent_id"),
                version_tag=payload.get("version_tag"),
            )
            await _ws_send(websocket, "personality_created", {"personality": p})

        elif msg_type == "update_personality":
            pid = int(payload.get("id", 0))
            if pid:
                p = manager.update(
                    pid,
                    name=payload.get("name"),
                    description=payload.get("description"),
                    system_prompt=payload.get("system_prompt"),
                    version_tag=payload.get("version_tag"),
                )
                await _ws_send(websocket, "personality_updated", {"personality": p})
                # 如果修改的是当前人格，刷新引用
                if current_personality and current_personality.get("id") == pid:
                    current_personality = p

        elif msg_type == "delete_personality":
            pid = int(payload.get("id", 0))
            if pid:
                ok = manager.delete(pid)
                await _ws_send(websocket, "personality_deleted", {"id": pid, "ok": ok})

        elif msg_type == "reseed_personalities":
            count = manager.reseed()
            current_personality = manager.get_default()
            plist = manager.list_all()
            grouped = manager.list_grouped()
            await _ws_send(websocket, "personalities_reseeded", {
                "count": count,
                "personalities": plist,
                "grouped": grouped,
                "current": current_personality.get("id"),
            })

    except Exception as exc:
        await _ws_send(websocket, "error", {"message": f"Personality operation failed: {exc}"})
        return None

    return current_personality


async def _ws_send(websocket: WebSocket, msg_type: str, payload: dict) -> None:
    """Safely send a JSON message over WebSocket."""
    try:
        await websocket.send_json({"type": msg_type, "payload": payload})
    except Exception:
        pass
