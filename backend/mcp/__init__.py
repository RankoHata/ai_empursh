"""MCP Manager — orchestrates multiple MCP Server connections.

Provides a unified interface for the chat engine to discover and call MCP tools,
regardless of transport (stdio or HTTP).
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

import yaml

from mcp.adapter import parse_mcp_name, is_mcp_tool
from mcp.errors import MCPConnectionError, MCPTimeoutError, MCPServerError
from mcp.stdio_client import MCPStdioClient
from mcp.http_client import MCPHTTPClient

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "mcp_servers.yaml"


class MCPManager:
    """Manages lifecycle of multiple MCP server connections.

    Loads server definitions from a YAML config file and provides
    unified tool discovery and invocation.

    Usage::

        mgr = MCPManager.from_config("mcp_servers.yaml")
        await mgr.connect_all()
        openai_tools = mgr.get_all_tools()
        result = await mgr.call_tool("mcp__filesystem__read_file", {"path": "foo.txt"})
        await mgr.disconnect_all()
    """

    def __init__(self):
        self._clients: dict[str, Any] = {}   # server_name → MCPStdioClient | MCPHTTPClient
        self._tool_map: dict[str, str] = {}  # mcp_tool_name → server_name

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config_path: str = None) -> "MCPManager":
        """Create an MCPManager from a YAML config file.

        Args:
            config_path: Path to mcp_servers.yaml. Defaults to
                         ``backend/mcp_servers.yaml``.

        Returns:
            An MCPManager with clients configured but not yet connected.
        """
        path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        if not path.exists():
            logger.warning("MCP config not found at %s; starting with no MCP servers", path)
            return cls()

        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

        servers = data.get("servers", [])
        if not servers:
            logger.info("No MCP servers configured")
            return cls()

        mgr = cls()

        for server_cfg in servers:
            name = server_cfg.get("name", "").strip()
            if not name:
                logger.warning("Skipping MCP server with empty name")
                continue

            transport = server_cfg.get("transport", "stdio")
            timeout = float(server_cfg.get("timeout", 30))

            try:
                if transport == "stdio":
                    command = server_cfg.get("command", "").strip()
                    if not command:
                        logger.warning("MCP[%s] Missing 'command' for stdio transport, skipping", name)
                        continue
                    args = server_cfg.get("args", [])
                    env = server_cfg.get("env", None)
                    cwd = server_cfg.get("cwd", None)

                    client = MCPStdioClient(
                        name=name,
                        command=command,
                        args=args,
                        env=env,
                        cwd=cwd,
                        timeout=timeout,
                    )
                elif transport == "http":
                    url = server_cfg.get("url", "").strip()
                    if not url:
                        logger.warning("MCP[%s] Missing 'url' for http transport, skipping", name)
                        continue
                    headers = server_cfg.get("headers", None)

                    client = MCPHTTPClient(
                        name=name,
                        url=url,
                        timeout=timeout,
                        headers=headers,
                    )
                else:
                    logger.warning("MCP[%s] Unknown transport '%s', skipping", name, transport)
                    continue

                mgr._clients[name] = client
                logger.info("MCP[%s] Configured: transport=%s", name, transport)

            except Exception as exc:
                logger.error("MCP[%s] Failed to configure: %s", name, exc)

        return mgr

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect_all(self) -> None:
        """Connect to all configured MCP servers in parallel.

        Failed connections are logged but do not prevent other servers
        from connecting.
        """
        if not self._clients:
            logger.info("No MCP servers to connect")
            return

        async def _connect_one(name: str, client) -> None:
            try:
                await client.connect()
                logger.info("MCP[%s] Connected — %d tools", name, len(client.get_raw_tools()))
            except Exception as exc:
                logger.error("MCP[%s] Failed to connect: %s", name, exc)
                # Remove this client so it doesn't interfere
                self._clients.pop(name, None)

        tasks = [
            asyncio.create_task(_connect_one(name, client))
            for name, client in self._clients.items()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Build tool → server map
        self._rebuild_tool_map()

        connected = len(self._clients)
        logger.info("MCP Manager: %d server(s) connected", connected)

    async def disconnect_all(self) -> None:
        """Disconnect all MCP servers in parallel."""
        async def _disconnect_one(name: str, client) -> None:
            try:
                await client.disconnect()
                logger.info("MCP[%s] Disconnected", name)
            except Exception as exc:
                logger.warning("MCP[%s] Error during disconnect: %s", name, exc)

        tasks = [
            asyncio.create_task(_disconnect_one(name, client))
            for name, client in self._clients.items()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._clients.clear()
        self._tool_map.clear()

    # ------------------------------------------------------------------
    # Tool discovery
    # ------------------------------------------------------------------

    def get_all_tools(self) -> list[dict[str, Any]]:
        """Return all MCP tools as OpenAI function calling schemas."""
        all_tools: list[dict[str, Any]] = []
        for name, client in self._clients.items():
            if client.connected:
                try:
                    all_tools.extend(client.get_tool_schemas())
                except Exception as exc:
                    logger.warning("MCP[%s] Error getting tool schemas: %s", name, exc)
        return all_tools

    # ------------------------------------------------------------------
    # Tool invocation
    # ------------------------------------------------------------------

    async def call_tool(self, mcp_name: str, arguments: dict) -> dict:
        """Invoke an MCP tool by its namespaced name.

        Args:
            mcp_name: The namespaced name, e.g. "mcp__filesystem__read_file".
            arguments: Tool arguments as a dict.

        Returns:
            The tool result dict.

        Raises:
            KeyError: If the tool name is not found.
            MCPConnectionError, MCPTimeoutError, MCPServerError: On failure.
        """
        parsed = parse_mcp_name(mcp_name)
        if parsed is None:
            raise KeyError(f"Not an MCP tool: {mcp_name}")

        server_name, tool_name = parsed
        client = self._clients.get(server_name)
        if client is None:
            raise KeyError(f"MCP server '{server_name}' not found (available: {list(self._clients.keys())})")

        if not client.connected:
            raise MCPConnectionError(f"MCP server '{server_name}' is not connected")

        logger.debug("MCP call: server=%s tool=%s args=%s",
                     server_name, tool_name, str(arguments)[:200])

        try:
            result = await client.call_tool(tool_name, arguments)
        except (MCPTimeoutError, MCPConnectionError, MCPServerError):
            raise
        except Exception as exc:
            logger.error("MCP[%s] Unexpected error calling '%s': %s", server_name, tool_name, exc)
            raise MCPServerError(-1, str(exc)) from exc

        return result

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def list_servers(self) -> list[dict[str, Any]]:
        """Return connection status for all servers."""
        return [
            {
                "name": name,
                "transport": "stdio" if isinstance(c, MCPStdioClient) else "http",
                "connected": c.connected,
                "tool_count": len(c.get_raw_tools()) if c.connected else 0,
                "tool_names": [t.get("name", "?") for t in c.get_raw_tools()] if c.connected else [],
            }
            for name, c in self._clients.items()
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _rebuild_tool_map(self) -> None:
        """Rebuild the tool_name → server_name lookup map."""
        self._tool_map.clear()
        for server_name, client in self._clients.items():
            if client.connected:
                for tool in client.get_raw_tools():
                    from mcp.adapter import make_mcp_name
                    mcp_name = make_mcp_name(server_name, tool.get("name", ""))
                    self._tool_map[mcp_name] = server_name
