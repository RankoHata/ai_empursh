"""人格统一管理器 — 加载、版本聚合、模板渲染、情绪标签提取."""

import logging
import re
from datetime import datetime
from typing import Any, Optional

from config import AppConfig
from db import personalities as personalities_db
from utils.template import render_prompt

logger = logging.getLogger(__name__)

# 版本标签 → 前端显示名
_VERSION_LABELS: dict[str, str] = {
    "simple": "简洁",
    "full": "完整",
    "arc": "深度",
}


class PersonalityManager:
    """人格统一管理器。main.py 通过此类进行所有人格操作。"""

    def __init__(self, config: AppConfig):
        self._config = config

    # ── CRUD 委托 ──

    def get(self, pid: int) -> Optional[dict[str, Any]]:
        return personalities_db.get_personality(pid)

    def get_default(self) -> dict[str, Any]:
        return personalities_db.get_default_personality()

    def list_all(self) -> list[dict[str, Any]]:
        return personalities_db.list_personalities()

    def create(self, **fields) -> dict[str, Any]:
        return personalities_db.create_personality(
            name=fields.get("name", ""),
            description=fields.get("description", ""),
            system_prompt=fields.get("system_prompt", ""),
            parent_id=fields.get("parent_id"),
            version_tag=fields.get("version_tag"),
            metadata=fields.get("metadata"),
        )

    def update(self, pid: int, **fields) -> Optional[dict[str, Any]]:
        return personalities_db.update_personality(
            pid,
            name=fields.get("name"),
            description=fields.get("description"),
            system_prompt=fields.get("system_prompt"),
            version_tag=fields.get("version_tag"),
            metadata=fields.get("metadata"),
        )

    def delete(self, pid: int) -> bool:
        return personalities_db.delete_personality(pid)

    # ── 版本聚合 ──

    def list_grouped(self) -> list[dict[str, Any]]:
        """返回聚合后的人格列表，供前端直接渲染选择器。

        返回格式:
        [
          {
            "id": 1, "name": "默认助手", "parent_id": None, "version_tag": None,
            "is_single": true, "versions": []
          },
          {
            "id": 101, "name": "阿尼斯", "parent_id": None, "version_tag": "simple",
            "is_single": false,
            "versions": [
              {"id": 101, "version_tag": "simple", "label": "简洁"},
              {"id": 102, "version_tag": "full", "label": "完整"},
            ]
          },
        ]
        """
        all_pers = self.list_all()
        roots = [p for p in all_pers if p.get("parent_id") is None]
        children = [p for p in all_pers if p.get("parent_id") is not None]

        result: list[dict[str, Any]] = []
        for root in roots:
            versions = [c for c in children if c["parent_id"] == root["id"]]
            for v in versions:
                v["label"] = _VERSION_LABELS.get(v.get("version_tag", ""), v.get("version_tag", ""))
            root["versions"] = versions
            root["is_single"] = len(versions) == 0
            result.append(root)
        return result

    # ── 模板渲染 ──

    def render_prompt(
        self,
        personality: dict[str, Any],
        extra_context: Optional[dict[str, Any]] = None,
        *,
        include_emotion: bool = True,
    ) -> str:
        """渲染 system_prompt 中的 Jinja2 模板变量。

        Args:
            personality: 人格记录（含 system_prompt, name, version_tag 等）
            extra_context: 额外的模板变量
            include_emotion: 是否追加情绪标签指令（默认 True 兼容旧调用方；
                             使用 PromptPipeline 时设为 False）

        Returns:
            渲染后的 system_prompt 字符串
        """
        now = datetime.now()
        ctx = {
            "user_name": self._config.user.get("name", "") or "用户",
            "current_time": now.strftime("%Y-%m-%d %H:%M"),
            "personality_name": personality.get("name", "AI 助理"),
            "version_tag": personality.get("version_tag") or "",
        }
        if extra_context:
            ctx.update(extra_context)

        rendered = render_prompt(personality.get("system_prompt", ""), ctx)

        if include_emotion:
            emotion_instruction = (
                "\n\n[系统指令] 在每次回复的最后一行，单独输出 [!emotion:标签!] 表示你当前的情绪语气。"
                "可用标签：happy, sad, angry, thinking, surprised, bored, idle。"
                "此标记不会显示给用户，请务必带上。"
            )
            return rendered + emotion_instruction
        return rendered

    # ── 种子管理 ──

    def reseed(self) -> int:
        """强制从 YAML 重新导入所有种子人格（覆盖已有种子数据）。"""
        return personalities_db.seed_personalities(force=True)

    # ── 情绪标签提取 ──

    def extract_emotion(self, response_text: str) -> tuple[str, str]:
        """从回复中提取并剥离 [!emotion:xxx!] 标签。

        Returns:
            (clean_text, emotion_label) — clean_text 不含标签
        """
        # Match both [!emotion:xxx!] and !emotion:xxx! (model may drop brackets)
        match = re.search(r'\[?!emotion:\s*(\w+)\s*!\]?', response_text)
        if match:
            emotion = match.group(1)
            clean = re.sub(r'\[?!emotion:\s*\w+\s*!\]?\s*', '', response_text)
            return clean, emotion
        return response_text, "idle"


# ── 单例工厂 ──

_manager: Optional[PersonalityManager] = None


def get_manager(config: Optional[AppConfig] = None) -> PersonalityManager:
    """获取 PersonalityManager 单例。"""
    global _manager
    if _manager is None:
        if config is None:
            config = AppConfig.get()
        _manager = PersonalityManager(config)
    return _manager


def ensure_seeded():
    """种子初始化（首次启动时从 YAML 导入）。"""
    personalities_db.seed_personalities()
