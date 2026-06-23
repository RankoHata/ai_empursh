"""PromptPipeline — 有序 prompt 片段列表，按序渲染拼接。"""

import logging
from typing import Any, Callable, Optional

from prompt.context import PromptContext

logger = logging.getLogger(__name__)

# A segment is a callable: (PromptContext) -> str | None
Segment = Callable[[PromptContext], Optional[str]]


class PromptPipeline:
    """管理 prompt 片段的组装管线。

    每个 segment 是纯函数，接收 PromptContext，返回字符串或 None。
    Pipeline 按注册顺序调用，跳过返回 None 的 segment，其余用双换行拼接。
    """

    def __init__(self, segments: Optional[list[tuple[str, Segment]]] = None):
        """Args:
            segments: 可选初始片段列表。每项 (name, segment_fn)。
        """
        self._segments: list[tuple[str, Segment]] = list(segments) if segments else []

    def add(self, name: str, segment: Segment) -> "PromptPipeline":
        """追加一个片段。返回 self 支持链式调用。"""
        self._segments.append((name, segment))
        return self

    def build(self, ctx: PromptContext) -> str:
        """按序调用所有 segment，拼接为完整 prompt。

        Args:
            ctx: PromptContext —— 所有条件 flag + 模板变量

        Returns:
            拼接后的完整 system prompt 字符串
        """
        parts: list[str] = []
        for name, segment in self._segments:
            try:
                result = segment(ctx)
                if result:
                    parts.append(result)
            except Exception as exc:
                logger.warning("Prompt segment '%s' failed: %s", name, exc)
        prompt = "\n\n".join(parts)
        logger.debug("Prompt built: %d segments → %d chars", len(parts), len(prompt))
        return prompt

    @staticmethod
    def default(personality_manager: Any, personality: dict) -> "PromptPipeline":
        """创建默认 pipeline：人格 → 情绪标签 → 紧凑模式。

        Args:
            personality_manager: PersonalityManager 实例（用于模板渲染）
            personality: 当前人格记录 dict

        Returns:
            配置好的 PromptPipeline
        """
        from prompt.segments.personality import personality_segment
        from prompt.segments.emotion import emotion_segment
        from prompt.segments.compact import compact_segment
        from prompt.segments.time_info import time_info_segment

        # Bind manager + personality data into the segment closures
        _pm = personality_manager
        _personality = personality

        return PromptPipeline([
            ("personality", lambda ctx: personality_segment(ctx, _pm, _personality)),
            ("time_info", time_info_segment),
            ("compact", compact_segment),
            ("emotion", emotion_segment),
        ])
