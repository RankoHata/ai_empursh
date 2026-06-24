"""Tests for routers/conversations: 对话管理 handlers."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routers.conversations import handle_conversations, is_conversation_msg


@pytest.fixture
def ws():
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture
def session():
    s = MagicMock()
    s.load_history = MagicMock()
    return s


class TestIsConversationMsg:
    def test_known_types(self):
        assert is_conversation_msg("delete_turn")
        assert is_conversation_msg("create_conversation")
        assert is_conversation_msg("list_conversations")
        assert is_conversation_msg("load_conversation")

    def test_unknown_type(self):
        assert not is_conversation_msg("chat")
        assert not is_conversation_msg("add_note")


class TestConversationHandlers:
    @pytest.mark.asyncio
    async def test_list_conversations(self, ws, session):
        with patch("routers.conversations.conv_db") as db:
            db.list_conversations.return_value = [{"id": "1", "title": "测试"}]
            cid, ti = await handle_conversations(ws, "list_conversations", {}, session, None, 0)
            ws.send_json.assert_called_once()
            args = ws.send_json.call_args[0][0]
            assert args["type"] == "conversations_list"

    @pytest.mark.asyncio
    async def test_create_conversation(self, ws, session):
        with patch("routers.conversations.conv_db") as db:
            db.create_conversation.return_value = {"id": "new1", "title": "新对话"}
            cid, ti = await handle_conversations(ws, "create_conversation", {"title": "test"}, session, None, 0)
            ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_conversation_resets_current(self, ws, session):
        with patch("routers.conversations.conv_db") as db:
            db.delete_conversation.return_value = True
            cid, ti = await handle_conversations(ws, "delete_conversation", {"conversation_id": "1"}, session, "1", 5)
            assert cid is None
            assert ti == 0

    @pytest.mark.asyncio
    async def test_load_conversation(self, ws, session):
        with patch("routers.conversations.conv_db") as db:
            db.get_conversation.return_value = {"id": "1", "title": "test"}
            db.build_history_from_turns.return_value = [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ]
            db.get_turn_count.return_value = 1
            cid, ti = await handle_conversations(ws, "load_conversation", {"conversation_id": "1"}, session, None, 0)
            session.load_history.assert_called_once()
            assert cid == "1"
            assert ti == 1

    @pytest.mark.asyncio
    async def test_get_turns(self, ws, session):
        with patch("routers.conversations.conv_db") as db:
            db.get_turns.return_value = [{"turn_index": 0, "user_content": "hi"}]
            cid, ti = await handle_conversations(ws, "get_turns", {"conversation_id": "1"}, session, "1", 0)
            ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_turn(self, ws, session):
        with patch("routers.conversations.conv_db") as db:
            db.delete_turn.return_value = True
            cid, ti = await handle_conversations(ws, "delete_turn", {"conversation_id": "1", "turn_index": 0}, session, "1", 0)
            ws.send_json.assert_called_once()
