"""Tests for the MCP module: protocol, adapter, manager, and stdio client."""

import asyncio
import json
import sys
import time
from pathlib import Path

import pytest

# Ensure backend is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.protocol import (
    build_request,
    build_notification,
    build_initialize_request,
    build_initialized_notification,
    build_tools_list_request,
    build_tools_call_request,
    parse_response,
    is_error,
    get_result,
    get_error,
)
from mcp.adapter import (
    make_mcp_name,
    parse_mcp_name,
    is_mcp_tool,
    mcp_tool_to_openai,
    mcp_tools_to_openai,
)
from mcp.errors import MCPError, MCPConnectionError, MCPTimeoutError, MCPProtocolError, MCPServerError
from mcp import MCPManager
from mcp.stdio_client import MCPStdioClient


# ======================================================================
# protocol.py tests
# ======================================================================

class TestProtocol:
    def test_build_request(self):
        data = build_request(1, "test/method", {"key": "val"})
        msg = json.loads(data.decode("utf-8"))
        assert msg["jsonrpc"] == "2.0"
        assert msg["id"] == 1
        assert msg["method"] == "test/method"
        assert msg["params"] == {"key": "val"}

    def test_build_notification(self):
        data = build_notification("notifications/test", {"x": 1})
        msg = json.loads(data.decode("utf-8"))
        assert msg["jsonrpc"] == "2.0"
        assert "id" not in msg
        assert msg["method"] == "notifications/test"

    def test_build_initialize_request(self):
        data = build_initialize_request(42)
        msg = json.loads(data.decode("utf-8"))
        assert msg["method"] == "initialize"
        assert msg["params"]["protocolVersion"] == "2024-11-05"
        assert "capabilities" in msg["params"]
        assert "clientInfo" in msg["params"]

    def test_build_initialized_notification(self):
        data = build_initialized_notification()
        msg = json.loads(data.decode("utf-8"))
        assert msg["method"] == "notifications/initialized"
        assert "id" not in msg

    def test_build_tools_list_request(self):
        data = build_tools_list_request(7)
        msg = json.loads(data.decode("utf-8"))
        assert msg["method"] == "tools/list"

    def test_build_tools_call_request(self):
        data = build_tools_call_request(3, "echo", {"msg": "hi"})
        msg = json.loads(data.decode("utf-8"))
        assert msg["method"] == "tools/call"
        assert msg["params"]["name"] == "echo"
        assert msg["params"]["arguments"] == {"msg": "hi"}

    def test_parse_response_success(self):
        raw = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"ok": True}})
        msg = parse_response(raw)
        assert not is_error(msg)
        assert get_result(msg) == {"ok": True}

    def test_parse_response_error(self):
        raw = json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": -1, "message": "fail"}})
        msg = parse_response(raw)
        assert is_error(msg)
        code, message, data = get_error(msg)
        assert code == -1
        assert message == "fail"

    def test_parse_response_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            parse_response("not json")


# ======================================================================
# adapter.py tests
# ======================================================================

class TestAdapter:
    def test_make_mcp_name(self):
        assert make_mcp_name("filesystem", "read_file") == "mcp__filesystem__read_file"
        assert make_mcp_name("monitor", "get_processes") == "mcp__monitor__get_processes"

    def test_parse_mcp_name_valid(self):
        result = parse_mcp_name("mcp__filesystem__read_file")
        assert result == ("filesystem", "read_file")

        result = parse_mcp_name("mcp__a__b")
        assert result == ("a", "b")

    def test_parse_mcp_name_builtin(self):
        assert parse_mcp_name("search_notes") is None
        assert parse_mcp_name("get_notes") is None

    def test_parse_mcp_name_invalid_prefix(self):
        assert parse_mcp_name("mcp__") is None
        assert parse_mcp_name("not_mcp__x__y") is None

    def test_is_mcp_tool(self):
        assert is_mcp_tool("mcp__fs__read") is True
        assert is_mcp_tool("search_notes") is False

    def test_mcp_tool_to_openai(self):
        mcp_tool = {
            "name": "echo",
            "description": "Echo back arguments",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Text to echo"},
                    "repeat": {"type": "integer", "description": "Repeat count"},
                },
                "required": ["message"],
            },
        }
        result = mcp_tool_to_openai("echo-server", mcp_tool)
        assert result["type"] == "function"
        fn = result["function"]
        assert fn["name"] == "mcp__echo-server__echo"
        assert fn["description"] == "Echo back arguments"
        assert fn["parameters"]["type"] == "object"
        assert "message" in fn["parameters"]["properties"]
        assert fn["parameters"]["required"] == ["message"]

    def test_mcp_tool_to_openai_cleans_schema_fields(self):
        mcp_tool = {
            "name": "test",
            "description": "Test",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "$comment": "should be stripped",
                        "description": "File path",
                    },
                },
            },
        }
        result = mcp_tool_to_openai("srv", mcp_tool)
        props = result["function"]["parameters"]["properties"]
        assert "$comment" not in props["path"]

    def test_mcp_tools_to_openai_batch(self):
        mcp_tools = [
            {"name": "t1", "description": "Tool 1", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "t2", "description": "Tool 2", "inputSchema": {"type": "object", "properties": {}}},
        ]
        results = mcp_tools_to_openai("srv", mcp_tools)
        assert len(results) == 2
        assert results[0]["function"]["name"] == "mcp__srv__t1"
        assert results[1]["function"]["name"] == "mcp__srv__t2"


# ======================================================================
# errors.py tests
# ======================================================================

class TestErrors:
    def test_mcp_server_error(self):
        err = MCPServerError(-32000, "Something went wrong", {"detail": "x"})
        assert err.code == -32000
        assert err.message == "Something went wrong"
        assert err.data == {"detail": "x"}
        assert str(err) == "Something went wrong"

    def test_mcp_timeout_is_also_asyncio_timeout(self):
        err = MCPTimeoutError("timed out")
        assert isinstance(err, asyncio.TimeoutError)


# ======================================================================
# MCPManager tests
# ======================================================================

class TestMCPManager:
    def test_empty_config(self):
        mgr = MCPManager()
        assert len(mgr._clients) == 0
        assert mgr.get_all_tools() == []

    def test_from_nonexistent_config(self):
        mgr = MCPManager.from_config("nonexistent.yaml")
        assert len(mgr._clients) == 0


# ======================================================================
# StdioClient integration test (requires echo server subprocess)
# ======================================================================

@pytest.mark.integration
class TestStdioClientIntegration:
    @pytest.mark.asyncio
    async def test_connect_and_list_tools(self):
        """Connect to the MCP echo server and fetch tools."""
        client = MCPStdioClient(
            name="echo",
            command=sys.executable,
            args=["-m", "tests.mcp_echo_server"],
            timeout=10,
        )
        try:
            await client.connect()
            assert client.connected

            tools = client.get_raw_tools()
            assert len(tools) == 2
            tool_names = [t["name"] for t in tools]
            assert "echo" in tool_names
            assert "get_time" in tool_names

            schemas = client.get_tool_schemas()
            assert len(schemas) == 2
            assert all(s["type"] == "function" for s in schemas)
            # Names should be namespaced
            assert schemas[0]["function"]["name"].startswith("mcp__echo__")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_call_echo_tool(self):
        """Call the echo tool and get a result."""
        client = MCPStdioClient(
            name="echo",
            command=sys.executable,
            args=["-m", "tests.mcp_echo_server"],
            timeout=10,
        )
        try:
            await client.connect()
            result = await client.call_tool("echo", {"message": "hello", "repeat": 3})
            assert result["content"][0]["text"] == "hellohellohello"
            assert result["echoed"] is True
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_call_get_time_tool(self):
        """Call the get_time tool."""
        client = MCPStdioClient(
            name="echo",
            command=sys.executable,
            args=["-m", "tests.mcp_echo_server"],
            timeout=10,
        )
        try:
            await client.connect()
            result = await client.call_tool("get_time", {"format": "iso"})
            assert "timestamp" in result
            assert result["format"] == "iso"
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_call_unknown_tool_raises(self):
        """Calling an unknown tool should raise MCPServerError."""
        client = MCPStdioClient(
            name="echo",
            command=sys.executable,
            args=["-m", "tests.mcp_echo_server"],
            timeout=10,
        )
        try:
            await client.connect()
            with pytest.raises(MCPServerError):
                await client.call_tool("nonexistent", {})
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_timeout(self):
        """A request should time out when the timeout is very short."""
        # Start a real echo server but use an absurdly short timeout
        client = MCPStdioClient(
            name="echo",
            command=sys.executable,
            args=["-m", "tests.mcp_echo_server"],
            timeout=0.001,  # 1ms — impossible to complete
        )
        try:
            with pytest.raises((MCPTimeoutError, MCPConnectionError, Exception)):
                await client.connect()
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect_then_reconnect(self):
        """Disconnect and reconnect should work."""
        client = MCPStdioClient(
            name="echo",
            command=sys.executable,
            args=["-m", "tests.mcp_echo_server"],
            timeout=10,
        )
        try:
            await client.connect()
            assert client.connected
            await client.disconnect()
            assert not client.connected

            # Reconnect
            await client.connect()
            assert client.connected
            tools = client.get_raw_tools()
            assert len(tools) == 2
        finally:
            await client.disconnect()


# ======================================================================
# MCPManager + StdioClient integration
# ======================================================================

@pytest.mark.integration
class TestMCPManagerIntegration:
    @pytest.mark.asyncio
    async def test_full_cycle(self):
        """End-to-end: MCPManager → echo server → tool call → result."""
        mgr = MCPManager()

        # Manually create and register a stdio client
        client = MCPStdioClient(
            name="echo",
            command=sys.executable,
            args=["-m", "tests.mcp_echo_server"],
            timeout=10,
        )
        mgr._clients["echo"] = client

        try:
            await mgr.connect_all()
            assert len(mgr._clients) == 1

            tools = mgr.get_all_tools()
            assert len(tools) == 2

            # Call via manager (namespaced name)
            result = await mgr.call_tool("mcp__echo__echo", {"message": "ping"})
            assert result["echoed"] is True

            # Check server status
            servers = await mgr.list_servers()
            assert len(servers) == 1
            assert servers[0]["name"] == "echo"
            assert servers[0]["connected"] is True
            assert servers[0]["tool_count"] == 2
        finally:
            await mgr.disconnect_all()
