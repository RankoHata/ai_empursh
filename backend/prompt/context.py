"""PromptContext — 所有 prompt 条件 flag 集中管理，不在业务代码中散落。"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PromptContext:
    """传递给每个 prompt segment 的上下文。

    新增条件只需加字段，segment 根据字段决定是否产出内容。
    """

    # ── 模板变量 ──
    user_name: str = "用户"
    personality_name: str = "AI 助理"
    version_tag: str = ""
    current_time: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))

    # ── 条件开关 ──
    compact_enabled: bool = False
    emotion_required: bool = True
    time_context_enabled: bool = False  # 未来 get_current_time 工具启用后改为 True

    # ── 扩展字段（模板中用 {{ extra.xxx }} 引用） ──
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.current_time:
            self.current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
