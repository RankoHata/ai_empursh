"""配置管理 + 文件保存 WS 消息处理。"""

import os
import logging
from pathlib import Path

from fastapi import WebSocket

logger = logging.getLogger(__name__)


def _timestamp():
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")


async def handle_config(
    websocket: WebSocket,
    msg_type: str,
    payload: dict,
    app_config,
    voice_tts,
) -> bool:
    """处理配置和文件保存消息。返回 True 表示已处理。"""
    try:
        if msg_type == "get_config":
            safe_cfg = {
                "model": {
                    "base_url": app_config.model["base_url"],
                    "api_key": ("***" + app_config.model.get("api_key", "")[-4:]
                                if len(app_config.model.get("api_key", "")) > 4 else "***"),
                    "model_name": app_config.model["model_name"],
                    "max_tokens": app_config.model["max_tokens"],
                },
                "voice": {
                    "stt_model": "base",
                    "tts_engine": voice_tts.get_engine_name(),
                    "tts_voice": app_config.voice.get("tts_voice", "zh-CN-XiaoxiaoNeural"),
                },
                "workspaces": app_config.workspaces,
                "user": app_config.user,
            }
            await _ws(websocket, "config", safe_cfg)
            return True

        elif msg_type == "update_config":
            updates = payload.get("updates", {})
            app_config.save(updates)
            await _ws(websocket, "config_updated", {"success": True})
            return True

        elif msg_type == "save_file":
            content = payload.get("content", "")
            filename = payload.get("filename", f"export_{_timestamp()}.md")
            output_dir = Path(os.path.expanduser("~/Desktop"))
            output_dir.mkdir(parents=True, exist_ok=True)
            file_path = output_dir / filename
            file_path.write_text(content, encoding="utf-8")
            logger.info("File saved: %s", file_path)
            await _ws(websocket, "file_saved", {"file_path": str(file_path)})
            return True

    except Exception as exc:
        logger.error("Config handler error: %s", exc)
        await _ws(websocket, "error", {"message": str(exc)})
        return True

    return False


def is_config_msg(msg_type: str) -> bool:
    return msg_type in ("get_config", "update_config", "save_file")


async def _ws(websocket: WebSocket, msg_type: str, payload: dict) -> None:
    try:
        await websocket.send_json({"type": msg_type, "payload": payload})
    except Exception:
        pass
