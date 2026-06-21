"""人格模块入口 — 薄包装层，导出 PersonalityManager 单例和种子函数."""

from .personality_manager import get_manager, ensure_seeded, PersonalityManager

__all__ = ["get_manager", "ensure_seeded", "PersonalityManager"]
