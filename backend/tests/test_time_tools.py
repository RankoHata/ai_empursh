"""Tests for get_current_time tool."""
import json
import pytest
from tools.time_tools import get_current_time_tool, _get_current_time


class TestGetCurrentTime:
    @pytest.mark.asyncio
    async def test_readable_format_has_timezone(self):
        result = await _get_current_time(format="readable")
        assert result["success"] is True
        assert "timezone" in result
        assert "本地时间" in result["message"]
        assert "换算" in result["message"]  # anti-timezone-confusion instruction

    @pytest.mark.asyncio
    async def test_iso_format(self):
        result = await _get_current_time(format="iso")
        assert result["success"] is True
        assert "T" in result["timestamp"]

    @pytest.mark.asyncio
    async def test_unix_format(self):
        result = await _get_current_time(format="unix")
        assert result["success"] is True
        assert isinstance(result["timestamp"], int)

    @pytest.mark.asyncio
    async def test_default_format_is_readable(self):
        result = await _get_current_time()
        assert result["success"] is True
        assert "年" in result["message"]

    @pytest.mark.asyncio
    async def test_ws_sender_ignored(self):
        """Verify _ws_sender is accepted but unused."""
        result = await _get_current_time(_ws_sender="mock")
        assert result["success"] is True

    def test_tool_definition_valid(self):
        td = get_current_time_tool
        assert td.name == "get_current_time"
        assert "format" in td.parameters
        assert len(td.required) == 0


class TestRegistryIntegration:
    def test_time_tool_in_default_registry(self):
        from tools import create_default_registry
        reg = create_default_registry()
        assert "get_current_time" in reg
        schemas = reg.get_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "get_current_time" in names
