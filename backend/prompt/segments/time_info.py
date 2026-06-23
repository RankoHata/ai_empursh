"""时间上下文片段 — 告诉 AI 用户的当前本地时间。"""

from prompt.context import PromptContext


def time_info_segment(ctx: PromptContext) -> str | None:
    """当 time_context_enabled 时，将当前时间作为系统信息注入。

    当前默认关闭 —— 等 get_current_time MCP 工具实现后启用。
    启用后 AI 不再依赖训练数据猜测时间。
    """
    if ctx.time_context_enabled:
        return (
            f"[系统信息] 用户当前的本地时间是 {ctx.current_time}（北京时间 UTC+8）。"
            "在回答时间相关问题时，请直接使用这个时间。"
        )
    return None
