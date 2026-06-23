"""Tests for routers/notes: public note and secret note message handlers."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routers.notes import handle_public_notes, handle_secret_message


@pytest.fixture
def ws():
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


# ── Public notes ──

class TestPublicNotes:
    @pytest.mark.asyncio
    async def test_add_note(self, ws):
        with patch("routers.notes.notes_db") as mock_db:
            mock_db.add_note.return_value = {"id": 1, "content": "test"}
            handled = await handle_public_notes(ws, "add_note", {"content": "test", "tags": ["tag1"]})
            assert handled is True
            ws.send_json.assert_called_once()
            args = ws.send_json.call_args[0][0]
            assert args["type"] == "note_saved"

    @pytest.mark.asyncio
    async def test_get_notes(self, ws):
        with patch("routers.notes.notes_db") as mock_db:
            mock_db.get_all_notes.return_value = [{"id": 1, "content": "note1"}]
            handled = await handle_public_notes(ws, "get_notes", {})
            assert handled is True
            ws.send_json.assert_called_once()
            args = ws.send_json.call_args[0][0]
            assert args["type"] == "notes_list"

    @pytest.mark.asyncio
    async def test_search_notes(self, ws):
        with patch("routers.notes.notes_db") as mock_db:
            mock_db.search_notes.return_value = [{"id": 1}]
            handled = await handle_public_notes(ws, "search_notes", {"query": "test"})
            assert handled is True
            args = ws.send_json.call_args[0][0]
            assert args["type"] == "search_results"

    @pytest.mark.asyncio
    async def test_delete_note(self, ws):
        with patch("routers.notes.notes_db") as mock_db:
            mock_db.delete_note.return_value = True
            handled = await handle_public_notes(ws, "delete_note", {"note_id": 1})
            assert handled is True
            args = ws.send_json.call_args[0][0]
            assert args["type"] == "note_deleted"

    @pytest.mark.asyncio
    async def test_delete_note_missing_id(self, ws):
        handled = await handle_public_notes(ws, "delete_note", {})
        assert handled is True
        args = ws.send_json.call_args[0][0]
        assert args["type"] == "error"

    @pytest.mark.asyncio
    async def test_unknown_type_returns_false(self, ws):
        handled = await handle_public_notes(ws, "unknown_msg", {})
        assert handled is False

    @pytest.mark.asyncio
    async def test_export_notes_no_ids(self, ws):
        handled = await handle_public_notes(ws, "export_notes", {"note_ids": []})
        assert handled is True
        args = ws.send_json.call_args[0][0]
        assert args["type"] == "error"


# ── Secret notes ──

class TestSecretNotes:
    @pytest.mark.asyncio
    async def test_secret_add(self, ws):
        with patch("routers.notes.secret_notes_db") as mock_db:
            mock_db.add_secret_note.return_value = {"id": 1}
            handled = await handle_secret_message(ws, "secret_add_note", {"content": "secret"})
            assert handled is True
            args = ws.send_json.call_args[0][0]
            assert args["type"] == "secret_note_saved"

    @pytest.mark.asyncio
    async def test_secret_get(self, ws):
        with patch("routers.notes.secret_notes_db") as mock_db:
            mock_db.get_all_secret_notes.return_value = []
            handled = await handle_secret_message(ws, "secret_get_notes", {})
            assert handled is True
            args = ws.send_json.call_args[0][0]
            assert args["type"] == "secret_notes_list"

    @pytest.mark.asyncio
    async def test_secret_search(self, ws):
        with patch("routers.notes.secret_notes_db") as mock_db:
            mock_db.search_secret_notes.return_value = [{"id": 1}]
            handled = await handle_secret_message(ws, "secret_search_notes", {"query": "test"})
            assert handled is True
            args = ws.send_json.call_args[0][0]
            assert args["type"] == "secret_search_results"

    @pytest.mark.asyncio
    async def test_secret_delete(self, ws):
        with patch("routers.notes.secret_notes_db") as mock_db:
            mock_db.delete_secret_note.return_value = True
            handled = await handle_secret_message(ws, "secret_delete_note", {"note_id": 1})
            assert handled is True
            args = ws.send_json.call_args[0][0]
            assert args["type"] == "secret_note_deleted"

    @pytest.mark.asyncio
    async def test_non_secret_type_returns_false(self, ws):
        handled = await handle_secret_message(ws, "add_note", {})
        assert handled is False
