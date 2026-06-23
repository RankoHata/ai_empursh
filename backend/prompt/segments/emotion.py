"""情绪标签指令片段。"""

from prompt.context import PromptContext

EMOTION_INSTRUCTION = (
    "[系统指令] 在每次回复的最后一行，单独输出 [!emotion:标签!] 表示你当前的情绪语气。"
    "可用标签：happy, sad, angry, thinking, surprised, bored, idle。"
    "此标记不会显示给用户，请务必带上。"
)


def emotion_segment(ctx: PromptContext) -> str | None:
    """当 emotion_required 时输出情绪标签指令。"""
    if ctx.emotion_required:
        return EMOTION_INSTRUCTION
    return None
