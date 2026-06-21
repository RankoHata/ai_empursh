"""JSON-RPC 2.0 message encoding/decoding for MCP.

MCP (Model Context Protocol) uses JSON-RPC 2.0 as its wire format.
Each message is a single line of JSON (no multi-line payloads).
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON-RPC 2.0 constants
# ---------------------------------------------------------------------------

JSONRPC_VERSION = "2.0"

# Standard JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# MCP standard method names
INITIALIZE = "initialize"
INITIALIZED = "notifications/initialized"
TOOLS_LIST = "tools/list"
TOOLS_CALL = "tools/call"
PING = "ping"

# MCP protocol version we declare
MCP_PROTOCOL_VERSION = "2024-11-05"

# Capabilities we advertise as a client
CLIENT_CAPABILITIES = {
    "roots": {"listChanged": True},
    "sampling": {},
}
CLIENT_INFO = {
    "name": "ai_empursh",
    "version": "1.0.0",
}


# ---------------------------------------------------------------------------
# Request / Response builders
# ---------------------------------------------------------------------------


def build_request(req_id: int, method: str, params: Optional[dict] = None) -> bytes:
    """Build a JSON-RPC 2.0 request.

    Returns a single line of JSON (utf-8 bytes).
    """
    msg: dict[str, Any] = {
        "jsonrpc": JSONRPC_VERSION,
        "id": req_id,
        "method": method,
        "params": params or {},
    }
    return (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")


def build_notification(method: str, params: Optional[dict] = None) -> bytes:
    """Build a JSON-RPC 2.0 notification (no id, no response expected)."""
    msg: dict[str, Any] = {
        "jsonrpc": JSONRPC_VERSION,
        "method": method,
        "params": params or {},
    }
    return (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")


def build_initialize_request(req_id: int) -> bytes:
    """Build the 'initialize' request for MCP handshake."""
    return build_request(req_id, INITIALIZE, {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": CLIENT_CAPABILITIES,
        "clientInfo": CLIENT_INFO,
    })


def build_initialized_notification() -> bytes:
    """Build the 'notifications/initialized' notification."""
    return build_notification(INITIALIZED)


def build_tools_list_request(req_id: int) -> bytes:
    """Build a 'tools/list' request."""
    return build_request(req_id, TOOLS_LIST)


def build_tools_call_request(req_id: int, tool_name: str, arguments: dict) -> bytes:
    """Build a 'tools/call' request."""
    return build_request(req_id, TOOLS_CALL, {
        "name": tool_name,
        "arguments": arguments,
    })


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def parse_response(data: str) -> dict:
    """Parse a JSON-RPC response line.

    Returns the full parsed dict.  Caller must check `is_error()`.

    Raises ``json.JSONDecodeError`` if the string is not valid JSON.
    """
    try:
        msg = json.loads(data)
    except json.JSONDecodeError:
        logger.warning("Failed to parse JSON-RPC response: %s", data[:200])
        raise
    return msg


def is_error(response: dict) -> bool:
    """Return True if the JSON-RPC response contains an ``error`` field."""
    return "error" in response


def get_result(response: dict) -> Any:
    """Extract the ``result`` field from a successful response."""
    return response.get("result")


def get_error(response: dict) -> tuple[int, str, Any]:
    """Extract (code, message, data) from an error response."""
    err = response.get("error", {})
    return err.get("code", -1), err.get("message", "Unknown error"), err.get("data")
