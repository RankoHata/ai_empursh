"""MCP HTTP client — connects to a remote MCP Server via HTTP.

Uses httpx for async HTTP communication.
Each tools/call is a separate POST request (request-response model).
"""

import json
import logging
from typing import Any, Optional

import httpx

from mcp.errors import MCPConnectionError, MCPTimeoutError, MCPServerError
from mcp.adapter import mcp_tools_to_openai

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_HEADERS = {"Content-Type": "application/json"}


class MCPHTTPClient:
    """Connects to a remote MCP Server via HTTP.

    Usage::

        client = MCPHTTPClient(name="remote-tools", url="http://127.0.0.1:9000/mcp")
        await client.connect()
        tools = await client.list_tools()
        result = await client.call_tool("some_tool", {"key": "val"})
        await client.disconnect()
    """

    def __init__(
        self,
        name: str,
        url: str,
        timeout: float = DEFAULT_TIMEOUT,
        headers: Optional[dict[str, str]] = None,
    ):
        self.name = name
        self.url = url.rstrip("/")
        self.timeout = timeout
        self._custom_headers = headers or {}

        # Runtime state
        self._http: Optional[httpx.AsyncClient] = None
        self._request_id = 0
        self._connected = False
        self._cached_tools: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Initialize the HTTP client, handshake, and cache the tool list."""
        if self._http is not None:
            await self.disconnect()

        logger.info("MCP[%s] Connecting to %s", self.name, self.url)

        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            headers={**DEFAULT_HEADERS, **self._custom_headers},
        )

        try:
            # --- Initialize handshake ---
            init_result = await self._rpc_call(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
                    "clientInfo": {"name": "ai_empursh", "version": "1.0.0"},
                },
            )
            logger.info(
                "MCP[%s] Initialize: protocol=%s server=%s",
                self.name,
                init_result.get("protocolVersion", "?"),
                init_result.get("serverInfo", {}).get("name", "?"),
            )

            # Send initialized notification
            await self._rpc_notify("notifications/initialized")

            # --- Fetch tool list ---
            tools_result = await self._rpc_call("tools/list")
            raw_tools = tools_result.get("tools", [])
            self._cached_tools = raw_tools
            logger.info(
                "MCP[%s] Got %d tools: %s",
                self.name, len(raw_tools),
                [t.get("name", "?") for t in raw_tools],
            )

        except Exception:
            await self._close_http()
            raise

        self._connected = True
        logger.info("MCP[%s] Connected successfully", self.name)

    async def disconnect(self) -> None:
        """Close the HTTP client."""
        self._connected = False
        await self._close_http()

    async def _close_http(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    # ------------------------------------------------------------------
    # Tool access
    # ------------------------------------------------------------------

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Return cached tool schemas in OpenAI format."""
        return mcp_tools_to_openai(self.name, self._cached_tools)

    def get_raw_tools(self) -> list[dict[str, Any]]:
        """Return raw MCP tool definitions."""
        return list(self._cached_tools)

    # ------------------------------------------------------------------
    # Tool invocation
    # ------------------------------------------------------------------

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Invoke a tool on the remote MCP server."""
        if not self._connected:
            raise MCPConnectionError(f"MCP[{self.name}] not connected")

        return await self._rpc_call("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

    # ------------------------------------------------------------------
    # Internal: JSON-RPC over HTTP
    # ------------------------------------------------------------------

    async def _rpc_call(self, method: str, params: Optional[dict] = None) -> Any:
        """Send a JSON-RPC request and return the result."""
        if self._http is None:
            raise MCPConnectionError(f"MCP[{self.name}] HTTP client not initialized")

        req_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }

        logger.debug("MCP[%s] REQ id=%s method=%s", self.name, req_id, method)

        try:
            resp = await self._http.post(self.url, json=payload)
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise MCPTimeoutError(
                f"MCP[{self.name}] Request {method} timed out after {self.timeout}s"
            ) from exc
        except httpx.HTTPError as exc:
            raise MCPConnectionError(
                f"MCP[{self.name}] HTTP error: {exc}"
            ) from exc

        try:
            body = resp.json()
        except Exception as exc:
            raise MCPConnectionError(
                f"MCP[{self.name}] Invalid JSON response: {exc}"
            ) from exc

        if "error" in body:
            err = body["error"]
            raise MCPServerError(
                err.get("code", -1),
                err.get("message", "Unknown error"),
                err.get("data"),
            )

        return body.get("result")

    async def _rpc_notify(self, method: str, params: Optional[dict] = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if self._http is None:
            return

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }

        try:
            await self._http.post(self.url, json=payload)
        except Exception as exc:
            logger.debug("MCP[%s] Notification '%s' failed (non-fatal): %s",
                        self.name, method, exc)

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    @property
    def connected(self) -> bool:
        return self._connected
