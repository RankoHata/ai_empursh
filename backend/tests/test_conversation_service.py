"""Tests for ConversationService — integration with real conv_db.

These tests verify parameter names match conv_db.add_turn() signature.
The previous bug (conversation_id vs conv_id, user_content vs user_message)
was NOT caught by mocked tests because mocks accept any kwargs.
"""
import os
import sqlite3
import tempfile

import pytest

from services.conversation_service import ConversationService


@pytest.fixture()
def db_path():
    """Create a temp SQLite DB path with conversation schema."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS conversation_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL REFERENCES conversations(id),
            turn_index INTEGER NOT NULL,
            user_message TEXT NOT NULL DEFAULT '',
            assistant_content TEXT NOT NULL DEFAULT '',
            trace_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT ''
        );
    """)
    conn.commit()
    conn.close()
    yield path
    os.unlink(path)


@pytest.fixture(autouse=True)
def setup_db(monkeypatch, db_path):
    """Redirect conv_db.get_connection() to use temp DB.
    Each call returns a NEW connection (matching real behavior where
    functions open/close their own connections)."""
    import db.conversations as conv_db

    original_get = conv_db.get_connection

    def _get_conn():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(conv_db, "get_connection", _get_conn)
    yield
    monkeypatch.setattr(conv_db, "get_connection", original_get)


class TestConversationServiceSaveTurn:
    """These tests would have caught the conversation_id/user_content parameter mismatch."""

    def test_save_turn_creates_conversation_auto(self, setup_db):
        svc = ConversationService()
        conv_id = svc.save_turn(
            conv_id=None,
            user_text="你好",
            assistant_content="你好！有什么可以帮助你的？",
            trace=[],
            turn_index=None,
        )
        assert conv_id is not None
        # Verify it was actually saved
        turns = svc.get_turns(conv_id)
        assert len(turns) == 1
        assert turns[0]["user_message"] == "你好"
        assert turns[0]["assistant_content"] == "你好！有什么可以帮助你的？"

    def test_save_turn_existing_conversation(self, setup_db):
        svc = ConversationService()
        # First turn
        conv_id = svc.save_turn(None, "msg1", "reply1", [], None)
        # Second turn — same conversation
        conv_id2 = svc.save_turn(conv_id, "msg2", "reply2", [], 1)
        assert conv_id2 == conv_id
        turns = svc.get_turns(conv_id)
        assert len(turns) == 2

    def test_list_conversations(self, setup_db):
        svc = ConversationService()
        svc.save_turn(None, "test", "reply", [], None)
        convs = svc.list_all()
        assert len(convs) >= 1

    def test_delete_turn(self, setup_db):
        svc = ConversationService()
        conv_id = svc.save_turn(None, "msg", "reply", [], None)
        assert svc.delete_turn(conv_id, 0) is True
        turns = svc.get_turns(conv_id)
        assert len(turns) == 0

    def test_load_history(self, setup_db):
        svc = ConversationService()
        conv_id = svc.save_turn(None, "hi", "hello", [{"step": "done"}], None)
        messages, count = svc.load_history(conv_id)
        assert count == 1
        assert len(messages) >= 1
