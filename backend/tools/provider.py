"""ToolProvider — 工具提供者的统一抽象接口。

所有工具来源（内置 ToolRegistry、MCP Manager、未来扩展）都实现此接口。
ToolDispatcher 聚合多个 provider，ChatSession 只依赖 ToolDispatcher。
"""

from abc import ABC, abstractmethod
from typing import Any


class ToolProvider(ABC):
    """工具提供者的抽象基类。

    每个 provider 负责：
    - 声明自己能提供的工具 schema（供 LLM function calling）
    - 按名称执行工具调用
    - 判断是否能处理某个工具名
    """

    @abstractmethod
    def get_schemas(self) -> list[dict[str, Any]]:
        """返回此 provider 提供的所有工具 schema（OpenAI 格式）。"""
        ...

    @abstractmethod
    async def execute(self, name: str, args: dict[str, Any]) -> str:
        """执行一个工具调用，返回 JSON 字符串结果。

        Args:
            name: 工具名（含前缀，如 'search_notes' 或 'mcp__echo_echo'）
            args: 调用参数

        Returns:
            JSON-encoded 结果字符串（兼容 OpenAI tool result content）
        """
        ...

    @abstractmethod
    def can_handle(self, name: str) -> bool:
        """判断是否能处理指定名称的工具调用。"""
        ...
