"""人格模板片段 — 从 DB 加载 system_prompt，Jinja2 渲染。"""

from typing import Any

from prompt.context import PromptContext
from utils.template import render_prompt


def personality_segment(
    ctx: PromptContext,
    personality_manager: Any,
    personality: dict,
) -> str:
    """渲染人格 system_prompt 模板。

    使用 PersonalityManager 的上下文变量（user_name, current_time 等），
    支持 {{ user_name }}、{{ current_time }}、{{ personality_name }} 等 Jinja2 变量。
    """
    system_prompt = personality.get("system_prompt", "")
    if not system_prompt:
        return ""

    template_ctx = {
        "user_name": ctx.user_name,
        "current_time": ctx.current_time,
        "personality_name": ctx.personality_name,
        "version_tag": ctx.version_tag or "",
    }
    if ctx.extra:
        template_ctx.update(ctx.extra)

    return render_prompt(system_prompt, template_ctx)
