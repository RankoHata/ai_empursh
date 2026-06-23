"""Tests for routers/personalities: CRUD and reseed handlers."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routers.personalities import handle_personalities


@pytest.fixture
def ws():
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture
def manager():
    mgr = MagicMock()
    mgr.list_all.return_value = [{"id": 1, "name": "默认助手"}]
    mgr.list_grouped.return_value = [{"id": 1, "name": "默认助手", "is_single": True}]
    mgr.get.return_value = {"id": 1, "name": "默认助手"}
    mgr.create.return_value = {"id": 2, "name": "new"}
    mgr.update.return_value = {"id": 1, "name": "updated"}
    mgr.delete.return_value = True
    mgr.reseed.return_value = 4
    mgr.get_default.return_value = {"id": 1, "name": "默认助手"}
    return mgr


class TestGetPersonalities:
    @pytest.mark.asyncio
    async def test_returns_list(self, ws, manager):
        current = {"id": 1}
        result = await handle_personalities(ws, "get_personalities", {}, manager, current)
        ws.send_json.assert_called_once()
        args = ws.send_json.call_args[0][0]
        assert args["type"] == "personalities_list"
        assert args["payload"]["current"] == 1

    @pytest.mark.asyncio
    async def test_returns_list_null_current(self, ws, manager):
        result = await handle_personalities(ws, "get_personalities", {}, manager, None)
        args = ws.send_json.call_args[0][0]
        assert args["payload"]["current"] is None


class TestSetPersonality:
    @pytest.mark.asyncio
    async def test_sets_and_returns(self, ws, manager):
        result = await handle_personalities(ws, "set_personality", {"personality_id": 1}, manager, None)
        assert result is not None
        assert result["id"] == 1
        ws.send_json.assert_called_once()


class TestCreatePersonality:
    @pytest.mark.asyncio
    async def test_creates(self, ws, manager):
        result = await handle_personalities(ws, "create_personality",
            {"name": "new", "description": "desc", "system_prompt": "prompt"}, manager, None)
        ws.send_json.assert_called_once()
        args = ws.send_json.call_args[0][0]
        assert args["type"] == "personality_created"


class TestUpdatePersonality:
    @pytest.mark.asyncio
    async def test_updates_non_current(self, ws, manager):
        result = await handle_personalities(ws, "update_personality",
            {"id": 2, "name": "updated"}, manager, {"id": 1})
        ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_current_refreshes_ref(self, ws, manager):
        manager.update.return_value = {"id": 1, "name": "refreshed"}
        result = await handle_personalities(ws, "update_personality",
            {"id": 1, "name": "refreshed"}, manager, {"id": 1})
        assert result is not None
        assert result["name"] == "refreshed"


class TestDeletePersonality:
    @pytest.mark.asyncio
    async def test_deletes(self, ws, manager):
        result = await handle_personalities(ws, "delete_personality", {"id": 1}, manager, None)
        ws.send_json.assert_called_once()
        args = ws.send_json.call_args[0][0]
        assert args["type"] == "personality_deleted"


class TestReseed:
    @pytest.mark.asyncio
    async def test_reseeds_and_returns_new_current(self, ws, manager):
        result = await handle_personalities(ws, "reseed_personalities", {}, manager, {"id": 99})
        assert result is not None
        assert result["id"] == 1  # from get_default()
        ws.send_json.assert_called_once()
        args = ws.send_json.call_args[0][0]
        assert args["type"] == "personalities_reseeded"
        assert args["payload"]["count"] == 4


class TestUnknownType:
    @pytest.mark.asyncio
    async def test_unknown_returns_none(self, ws, manager):
        result = await handle_personalities(ws, "bogus_type", {}, manager, None)
        assert result is None
