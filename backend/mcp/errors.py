"""MCP-specific exceptions."""

import asyncio


class MCPError(Exception):
    """Base exception for MCP errors."""


class MCPConnectionError(MCPError):
    """Failed to connect to an MCP Server."""


class MCPTimeoutError(MCPError, asyncio.TimeoutError):
    """An MCP request timed out."""


class MCPProtocolError(MCPError):
    """Invalid or unexpected JSON-RPC response."""


class MCPServerError(MCPError):
    """The MCP Server returned an error response."""

    def __init__(self, code: int, message: str, data: object = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data
