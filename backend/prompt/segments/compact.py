"""紧凑模式指令片段。"""

from prompt.context import PromptContext

COMPACT_INSTRUCTION = (
    "[系统指令-紧凑模式] 回复尽量紧凑简洁："
    "避免多余空行，段落之间最多一个空行；"
    "力求简洁、直接，不写冗余的礼貌用语和铺垫。"
)


def compact_segment(ctx: PromptContext) -> str | None:
    """当 compact_enabled 时输出紧凑模式指令。"""
    if ctx.compact_enabled:
        return COMPACT_INSTRUCTION
    return None
