"""ToolDispatcher — 聚合多个 ToolProvider，统一路由工具调用。

ChatSession 只依赖 ToolDispatcher，不感知工具来源
（内置 ToolRegistry、MCP、未来扩展）。
"""

import logging
from typing import Any

from tools.provider import ToolProvider
from mcp.adapter import is_mcp_tool

logger = logging.getLogger(__name__)


class ToolDispatcher:
    """聚合多个 ToolProvider，提供统一的工具查询和执行。

    Usage:
        dispatcher = ToolDispatcher()
        dispatcher.register(registry_provider)
        dispatcher.register(mcp_provider)
        schemas = dispatcher.get_all_schemas()
        result = await dispatcher.execute("search_notes", {"query": "test"})
    """

    def __init__(self):
        self._providers: list[ToolProvider] = []

    def register(self, provider: ToolProvider) -> None:
        """注册一个工具提供者。后注册的优先级更高（同名覆盖查询）。"""
        self._providers.append(provider)
        logger.info("ToolDispatcher: registered provider %s", type(provider).__name__)

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """聚合所有 provider 的工具 schema。"""
        schemas: list[dict[str, Any]] = []
        for provider in self._providers:
            schemas.extend(provider.get_schemas())
        return schemas

    async def execute(self, name: str, args: dict[str, Any]) -> str:
        """将工具调用路由到能处理它的第一个 provider。

        Args:
            name: 工具名（如 'search_notes' 或 'mcp__echo_echo'）
            args: 调用参数

        Returns:
            JSON-encoded 结果字符串

        Raises:
            ValueError: 没有 provider 能处理该工具
        """
        for provider in self._providers:
            if provider.can_handle(name):
                return await provider.execute(name, args)
        raise ValueError(f"No provider can handle tool: {name}")

    def can_handle(self, name: str) -> bool:
        """判断是否有 provider 能处理该工具。"""
        return any(p.can_handle(name) for p in self._providers)

    def __len__(self) -> int:
        return len(self._providers)
