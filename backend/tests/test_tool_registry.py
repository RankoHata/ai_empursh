"""Tests for ToolRegistry: registration, schema generation, execution, error handling."""
import json
import asyncio

import pytest

from tools.base import ToolDefinition
from tools import ToolRegistry, create_default_registry


# ── Helpers ──

async def _echo(message: str = "hello", repeat: int = 1, _ws_sender=None) -> dict:
    return {"success": True, "data": message * repeat, "count": 1, "message": "ok"}


async def _slow_tool(wait: float = 5.0, _ws_sender=None) -> dict:
    await asyncio.sleep(wait)
    return {"success": True}


async def _failing_tool(_ws_sender=None) -> dict:
    raise ValueError("simulated failure")


# ── Registration ──

class TestRegistration:
    def test_register_single_tool(self):
        reg = ToolRegistry()
        tool = ToolDefinition(name="echo", description="Echo back", parameters={}, required=[], executor=_echo)
        reg.register(tool)
        assert "echo" in reg
        assert len(reg) == 1
        assert reg.tool_names == ["echo"]

    def test_register_overwrite_warns(self, caplog):
        reg = ToolRegistry()
        t1 = ToolDefinition(name="echo", description="v1", parameters={}, required=[], executor=_echo)
        t2 = ToolDefinition(name="echo", description="v2", parameters={}, required=[], executor=_echo)
        reg.register(t1)
        reg.register(t2)
        assert "Overwriting" in caplog.text

    def test_register_all(self):
        reg = ToolRegistry()
        tools = [
            ToolDefinition(name="a", description="", parameters={}, required=[], executor=_echo),
            ToolDefinition(name="b", description="", parameters={}, required=[], executor=_echo),
        ]
        reg.register_all(tools)
        assert len(reg) == 2

    def test_unregister(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="x", description="", parameters={}, required=[], executor=_echo))
        reg.unregister("x")
        assert "x" not in reg
        assert len(reg) == 0


# ── Schema generation ──

class TestSchemas:
    def test_get_schemas_format(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(
            name="add",
            description="Add numbers",
            parameters={"a": {"type": "integer"}, "b": {"type": "integer"}},
            required=["a"],
            executor=_echo,
        ))
        schemas = reg.get_schemas()
        assert len(schemas) == 1
        s = schemas[0]
        assert s["type"] == "function"
        assert s["function"]["name"] == "add"
        assert s["function"]["parameters"]["required"] == ["a"]
        assert "a" in s["function"]["parameters"]["properties"]

    def test_get_schemas_filtered(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="a", description="", parameters={}, required=[], executor=_echo))
        reg.register(ToolDefinition(name="b", description="", parameters={}, required=[], executor=_echo))
        schemas = reg.get_schemas(tool_names=["a"])
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "a"

    def test_get_for_skill_no_restriction(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="t1", description="", parameters={}, required=[], executor=_echo))
        schemas = reg.get_for_skill({"allowed_tools": []})
        assert len(schemas) == 1  # empty allowed = all

    def test_get_for_skill_restricted(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="t1", description="", parameters={}, required=[], executor=_echo))
        reg.register(ToolDefinition(name="t2", description="", parameters={}, required=[], executor=_echo))
        schemas = reg.get_for_skill({"allowed_tools": ["t1"]})
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "t1"


# ── Execution ──

class TestExecution:
    @pytest.mark.asyncio
    async def test_execute_success(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="echo", description="", parameters={}, required=[], executor=_echo))
        result = await reg.execute("echo", {"message": "hi", "repeat": 2})
        data = json.loads(result)
        assert data["success"] is True
        assert data["data"] == "hihi"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        reg = ToolRegistry()
        result = await reg.execute("nonexistent", {})
        data = json.loads(result)
        assert data["success"] is False
        assert "未知工具" in data["message"]

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="slow", description="", parameters={}, required=[], executor=_slow_tool))
        # Reduce timeout for speed
        import tools as tools_mod
        old_timeout = tools_mod.DEFAULT_TOOL_TIMEOUT
        tools_mod.DEFAULT_TOOL_TIMEOUT = 0.1
        try:
            result = await reg.execute("slow", {"wait": 5.0})
            data = json.loads(result)
            assert data["success"] is False
            assert "超时" in data["message"]
        finally:
            tools_mod.DEFAULT_TOOL_TIMEOUT = old_timeout

    @pytest.mark.asyncio
    async def test_execute_exception(self):
        reg = ToolRegistry()
        reg.register(ToolDefinition(name="fail", description="", parameters={}, required=[], executor=_failing_tool))
        result = await reg.execute("fail", {})
        data = json.loads(result)
        assert data["success"] is False
        assert "simulated failure" in data["message"]

    @pytest.mark.asyncio
    async def test_ws_sender_injected(self):
        """Verify _ws_sender is passed to executor."""
        captured = []

        async def _capture(message: str = "", _ws_sender=None) -> dict:
            captured.append(_ws_sender)
            return {"success": True}

        reg = ToolRegistry()
        reg.register(ToolDefinition(name="cap", description="", parameters={}, required=[], executor=_capture))
        reg._ws_sender = "mock_sender"
        await reg.execute("cap", {"message": "test"})
        assert captured[0] == "mock_sender"


# ── Default registry ──

class TestCreateDefaultRegistry:
    def test_has_note_tools(self):
        reg = create_default_registry()
        names = reg.tool_names
        assert "search_notes" in names
        assert "get_notes" in names
        assert "add_note" in names
        assert "search_secret_notes" in names

    def test_contains_magic(self):
        reg = create_default_registry()
        assert "search_notes" in reg
        assert "made_up_tool" not in reg
