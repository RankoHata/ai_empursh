"""Minimal MCP stdio server for testing.

Implements the MCP JSON-RPC handshake and provides two echo tools:
  - echo: Returns the arguments as-is (for basic call verification).
  - get_time: Returns the current server time (for argument-free testing).

Usage:
    python -m tests.mcp_echo_server
"""

import json
import sys
from datetime import datetime


def log(msg: str) -> None:
    """Write log to stderr (stdout is reserved for JSON-RPC)."""
    print(f"[mcp_echo] {msg}", file=sys.stderr, flush=True)


def send_response(resp: dict) -> None:
    """Write a JSON-RPC response line to stdout."""
    line = json.dumps(resp, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def handle_request(req: dict) -> dict | None:
    """Handle a single JSON-RPC request. Returns the response dict."""
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    # --- initialize ---
    if method == "initialize":
        log(f"initialize: protocol={params.get('protocolVersion')} client={params.get('clientInfo', {}).get('name')}")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": "echo-server",
                    "version": "1.0.0",
                },
            },
        }

    # --- tools/list ---
    elif method == "tools/list":
        log("tools/list")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo back the provided arguments. Use for testing tool calls.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "message": {
                                    "type": "string",
                                    "description": "The message to echo back",
                                },
                                "repeat": {
                                    "type": "integer",
                                    "description": "Number of times to repeat (default: 1)",
                                },
                            },
                            "required": ["message"],
                        },
                    },
                    {
                        "name": "get_time",
                        "description": "Get the current server timestamp. Use for testing argument-free tool calls.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "format": {
                                    "type": "string",
                                    "description": "Time format: 'iso' or 'unix' (default: 'iso')",
                                },
                            },
                        },
                    },
                ],
            },
        }

    # --- tools/call ---
    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        log(f"tools/call: {tool_name} args={json.dumps(arguments, ensure_ascii=False)[:120]}")

        if tool_name == "echo":
            message = arguments.get("message", "hello")
            repeat = int(arguments.get("repeat", 1))
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": message * repeat}],
                    "original_args": arguments,
                    "echoed": True,
                },
            }
        elif tool_name == "get_time":
            fmt = arguments.get("format", "iso")
            if fmt == "unix":
                import time
                timestamp = int(time.time())
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": str(timestamp)}],
                        "timestamp": timestamp,
                        "format": "unix",
                    },
                }
            else:
                now = datetime.now().isoformat()
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": now}],
                        "timestamp": now,
                        "format": "iso",
                    },
                }
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}",
                },
            }

    # --- ping ---
    elif method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {},
        }

    # --- unknown method ---
    else:
        log(f"Unknown method: {method}")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }


def handle_notification(notif: dict) -> None:
    """Handle a JSON-RPC notification (no response needed)."""
    method = notif.get("method", "")
    log(f"notification: {method}")


def main() -> None:
    """Main loop: read JSON-RPC lines from stdin, write responses to stdout."""
    log("MCP Echo Server starting...")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            log(f"Invalid JSON: {exc}")
            continue

        if "id" in msg and "method" in msg:
            # It's a request
            try:
                response = handle_request(msg)
                if response:
                    send_response(response)
            except Exception as exc:
                log(f"Error handling request: {exc}")
                send_response({
                    "jsonrpc": "2.0",
                    "id": msg.get("id"),
                    "error": {"code": -32603, "message": str(exc)},
                })
        elif "method" in msg:
            # It's a notification
            handle_notification(msg)
        else:
            log(f"Unknown message format: {str(msg)[:120]}")

    log("MCP Echo Server exiting.")


if __name__ == "__main__":
    main()
