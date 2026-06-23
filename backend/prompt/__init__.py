"""Prompt 组装管线 — 消除硬编码，所有 prompt 片段集中在 segments/ 目录。

Usage:
    from prompt import PromptPipeline, PromptContext
    pipeline = PromptPipeline.default(personality_manager, personality)
    prompt = pipeline.build(PromptContext(user_name="张三", compact_enabled=True))
"""

from prompt.pipeline import PromptPipeline
from prompt.context import PromptContext

__all__ = ["PromptPipeline", "PromptContext"]
