"""对话生命周期服务 — 创建、持久化、加载。

独立于传输层，可被 WS handler 或 HTTP endpoint 复用。
"""

import logging
from typing import Any, Optional

from db import conversations as conv_db

logger = logging.getLogger(__name__)


class ConversationService:
    """管理对话的创建、自动持久化、加载。

    替代 main.py 中散落的 conv_db 调用，
    将对话生命周期逻辑集中到一处。
    """

    def __init__(self, explicit_save: bool = False):
        self._explicit_save = explicit_save

    # ── CRUD 委托 ──

    def create(self, title: str = "新对话") -> dict:
        return conv_db.create_conversation(title=title)

    def list_all(self) -> list[dict]:
        return conv_db.list_conversations()

    def get(self, conv_id: str) -> Optional[dict]:
        return conv_db.get_conversation(conv_id)

    def delete(self, conv_id: str) -> bool:
        return conv_db.delete_conversation(conv_id)

    def rename(self, conv_id: str, title: str) -> bool:
        return conv_db.update_conversation_title(conv_id, title)

    def load_history(self, conv_id: str) -> tuple[list[dict], int]:
        """加载对话历史。返回 (messages, turn_count)。"""
        conv = conv_db.get_conversation(conv_id)
        if not conv:
            return [], 0
        messages = conv_db.build_history_from_turns(conv_id)
        count = conv_db.get_turn_count(conv_id)
        logger.info("Loaded conversation %s: %d turns, %d messages",
                     conv_id, count, len(messages))
        return messages, count

    # ── 持久化 ──

    def save_turn(
        self,
        conv_id: str,
        user_text: str,
        assistant_content: str,
        trace: list[dict],
        turn_index: Optional[int] = None,
    ) -> str:
        """保存一轮对话。若 explicit_save=False（自动模式），首次对话自动创建。

        Returns:
            conv_id (可能新建)
        """
        if self._explicit_save and not conv_id:
            return conv_id  # 显式模式：没有对话 ID 就不保存

        if not conv_id:
            conv = self.create(title=user_text)
            conv_id = conv["id"]
            turn_index = 0
            logger.info("Auto-created conversation %s", conv_id)
        elif not conv_db.get_conversation(conv_id):
            conv = self.create(title=user_text)
            conv_id = conv["id"]
            turn_index = 0
            logger.info("Conversation lost, auto-created %s", conv_id)

        conv_db.add_turn(
            conv_id=conv_id,
            turn_index=turn_index,
            user_message=user_text,
            assistant_content=assistant_content,
            trace=trace,
        )
        return conv_id

    def get_turns(self, conv_id: str) -> list[dict]:
        return conv_db.get_turns(conv_id)

    def delete_turn(self, conv_id: str, turn_index: int) -> bool:
        return conv_db.delete_turn(conv_id, turn_index)
