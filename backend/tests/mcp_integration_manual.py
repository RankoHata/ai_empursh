"""Standalone integration test script for MCP stdio client.

Runs directly without pytest-asyncio:  python tests/test_mcp_integration.py
"""

import asyncio
import sys
from pathlib import Path

# Ensure backend is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.stdio_client import MCPStdioClient
from mcp import MCPManager
from mcp.errors import MCPServerError, MCPConnectionError


PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] {name}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name}  --  {detail}")


async def test_connect_and_list_tools():
    """Connect to echo server and fetch tool list."""
    print("\n--- Test: connect_and_list_tools ---")
    client = MCPStdioClient(
        name="echo",
        command=sys.executable,
        args=["-m", "tests.mcp_echo_server"],
        timeout=10,
    )
    try:
        await client.connect()
        check("connected", client.connected)

        tools = client.get_raw_tools()
        check("got 2 tools", len(tools) == 2, f"got {len(tools)}")

        tool_names = [t["name"] for t in tools]
        check("has echo tool", "echo" in tool_names)
        check("has get_time tool", "get_time" in tool_names)

        schemas = client.get_tool_schemas()
        check("schemas in OpenAI format", len(schemas) == 2 and all(
            s["type"] == "function" for s in schemas
        ))
        check("schema namespaced", schemas[0]["function"]["name"].startswith("mcp__echo__"))
    finally:
        await client.disconnect()
        check("disconnected", not client.connected)


async def test_call_echo_tool():
    """Call echo tool and verify result."""
    print("\n--- Test: call_echo_tool ---")
    client = MCPStdioClient(
        name="echo",
        command=sys.executable,
        args=["-m", "tests.mcp_echo_server"],
        timeout=10,
    )
    try:
        await client.connect()
        result = await client.call_tool("echo", {"message": "hello", "repeat": 3})
        check("echo repeated", result["content"][0]["text"] == "hellohellohello",
              f"got: {result.get('content', [{}])[0].get('text', '?')}")
        check("echoed flag", result.get("echoed") is True)
        check("original args preserved", result.get("original_args") == {"message": "hello", "repeat": 3})
    finally:
        await client.disconnect()


async def test_call_get_time():
    """Call get_time tool."""
    print("\n--- Test: call_get_time ---")
    client = MCPStdioClient(
        name="echo",
        command=sys.executable,
        args=["-m", "tests.mcp_echo_server"],
        timeout=10,
    )
    try:
        await client.connect()
        result = await client.call_tool("get_time", {"format": "iso"})
        check("has timestamp", "timestamp" in result)
        check("format is iso", result.get("format") == "iso")

        result2 = await client.call_tool("get_time", {"format": "unix"})
        check("unix timestamp is int", isinstance(result2.get("timestamp"), int),
              f"got type {type(result2.get('timestamp'))}")
    finally:
        await client.disconnect()


async def test_call_unknown_tool():
    """Unknown tool should raise error."""
    print("\n--- Test: call_unknown_tool ---")
    client = MCPStdioClient(
        name="echo",
        command=sys.executable,
        args=["-m", "tests.mcp_echo_server"],
        timeout=10,
    )
    try:
        await client.connect()
        try:
            await client.call_tool("nonexistent", {})
            check("should have raised", False, "No exception was raised")
        except MCPServerError as e:
            check("raised MCPServerError", True)
            check("has error code -32601", e.code == -32601, f"code={e.code}")
        except Exception as e:
            check("raised MCPServerError", False, f"raised {type(e).__name__}: {e}")
    finally:
        await client.disconnect()


async def test_reconnect():
    """Disconnect then reconnect."""
    print("\n--- Test: reconnect ---")
    client = MCPStdioClient(
        name="echo",
        command=sys.executable,
        args=["-m", "tests.mcp_echo_server"],
        timeout=10,
    )
    try:
        await client.connect()
        check("first connect", client.connected)
        await client.disconnect()
        check("first disconnect", not client.connected)

        await client.connect()
        check("reconnected", client.connected)
        tools = client.get_raw_tools()
        check("tools after reconnect", len(tools) == 2)

        # Verify still works
        result = await client.call_tool("echo", {"message": "ping"})
        check("call after reconnect", result["echoed"] is True)
    finally:
        await client.disconnect()


async def test_mcp_manager_full_cycle():
    """MCPManager full cycle with stdio client."""
    print("\n--- Test: mcp_manager_full_cycle ---")
    mgr = MCPManager()

    client = MCPStdioClient(
        name="echo",
        command=sys.executable,
        args=["-m", "tests.mcp_echo_server"],
        timeout=10,
    )
    mgr._clients["echo"] = client

    try:
        await mgr.connect_all()
        check("manager connected", len(mgr._clients) == 1)

        tools = mgr.get_all_tools()
        check("manager has 2 tools", len(tools) == 2)

        # Call via manager with namespaced name
        result = await mgr.call_tool("mcp__echo__echo", {"message": "via_manager"})
        check("manager call echo", result["echoed"] is True)

        # List servers
        servers = await mgr.list_servers()
        check("list servers", len(servers) == 1)
        check("server connected", servers[0]["connected"] is True)
        check("server tool count", servers[0]["tool_count"] == 2)
    finally:
        await mgr.disconnect_all()
        check("all disconnected", len(mgr._clients) == 0)


async def test_invalid_command():
    """Starting a process that doesn't exist should fail gracefully."""
    print("\n--- Test: invalid_command ---")
    client = MCPStdioClient(
        name="bad",
        command="nonexistent_binary_xyz_123",
        args=[],
        timeout=5,
    )
    try:
        await client.connect()
        check("should have failed", False, "Connect succeeded for nonexistent command")
    except (MCPConnectionError, FileNotFoundError, Exception) as e:
        check("raised error on invalid command", True, f"({type(e).__name__}: {e})")


async def main():
    global PASSED, FAILED
    print("=" * 60)
    print("MCP Integration Tests")
    print("=" * 60)

    for test_func in [
        test_connect_and_list_tools,
        test_call_echo_tool,
        test_call_get_time,
        test_call_unknown_tool,
        test_reconnect,
        test_mcp_manager_full_cycle,
        test_invalid_command,
    ]:
        try:
            await test_func()
        except Exception as exc:
            FAILED += 1
            print(f"  [FAIL] Unhandled exception: {type(exc).__name__}: {exc}")

    print("\n" + "=" * 60)
    print(f"Results: {PASSED} passed, {FAILED} failed")
    print("=" * 60)

    return FAILED == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
