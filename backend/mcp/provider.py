"""MCPToolProvider — 将 MCPManager 适配为 ToolProvider 接口。"""

import logging
from typing import Any

from tools.provider import ToolProvider

logger = logging.getLogger(__name__)


class MCPToolProvider(ToolProvider):
    """将 MCPManager 包装为 ToolProvider，统一工具调用入口。"""

    def __init__(self, mcp_manager: Any):
        self._mcp = mcp_manager

    def get_schemas(self) -> list[dict[str, Any]]:
        """返回所有 MCP 工具 schema。"""
        if self._mcp is None:
            return []
        return self._mcp.get_all_tools()

    async def execute(self, name: str, args: dict[str, Any]) -> str:
        """执行 MCP 工具调用。"""
        import json
        raw_result = await self._mcp.call_tool(name, args)
        if isinstance(raw_result, dict):
            if "success" not in raw_result:
                raw_result = {
                    "success": True,
                    "data": raw_result,
                    "message": "MCP 工具执行完成",
                }
            return json.dumps(raw_result, ensure_ascii=False)
        return json.dumps({"success": True, "data": raw_result, "message": "OK"}, ensure_ascii=False)

    def can_handle(self, name: str) -> bool:
        """MCP 工具名以 mcp__ 开头。"""
        from mcp.adapter import is_mcp_tool
        return is_mcp_tool(name)
