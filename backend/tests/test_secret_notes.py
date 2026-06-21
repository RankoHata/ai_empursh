"""Unit tests for secret knowledge items CRUD — uses temp-file SQLite."""

import pytest
import sqlite3
import tempfile
import os


@pytest.fixture(autouse=True)
def mock_db_connection(monkeypatch):
    """Replace get_connection with a temp-file SQLite database."""
    import db.secret_notes as mod
    import db.init_db as init_db_mod

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    def _temp_conn(scope="secret"):
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(mod, "get_connection", _temp_conn)
    monkeypatch.setattr(init_db_mod, "get_connection", _temp_conn)

    # Initialize schema once
    conn = _temp_conn()
    from db.init_db import DDL_KNOWLEDGE
    conn.executescript(DDL_KNOWLEDGE)
    conn.commit()
    conn.close()

    yield

    try:
        os.unlink(db_path)
    except OSError:
        pass


class TestAddSecretNote:
    def test_add_and_tags(self, mock_db_connection):
        from db.secret_notes import add_secret_note
        note = add_secret_note("My password is hunter2", tags=["finance"], title="Bank")
        assert note["id"] == 1
        assert note["source_type"] == "manual"
        assert note["content_raw"] == "My password is hunter2"
        assert note["tags"] == ["finance"]
        assert note["title"] == "Bank"

    def test_content_plain_strips_markdown(self, mock_db_connection):
        from db.secret_notes import add_secret_note
        note = add_secret_note("**Secret** data")
        assert "**" not in note["content_plain"]
        assert "Secret" in note["content_plain"]


class TestSearchSecretNotes:
    @pytest.fixture
    def secret_samples(self, mock_db_connection):
        from db.secret_notes import add_secret_note
        add_secret_note("Secret API key sk-abc123", tags=["api"], title="API Key")
        add_secret_note("Bank card 1234-5678", tags=["finance"], title="Card")
        add_secret_note("Public looking note", tags=["public"], title="Note")

    def test_search_finds_match(self, secret_samples):
        from db.secret_notes import search_secret_notes
        results = search_secret_notes("API")
        assert len(results) == 1
        assert "API" in results[0]["title"]

    def test_search_by_tag(self, secret_samples):
        from db.secret_notes import search_secret_notes
        results = search_secret_notes(tags=["finance"])
        assert len(results) == 1
        assert results[0]["title"] == "Card"

    def test_search_no_match(self, secret_samples):
        from db.secret_notes import search_secret_notes
        results = search_secret_notes("nonexistent")
        assert results == []


class TestDeleteSecretNote:
    def test_delete(self, mock_db_connection):
        from db.secret_notes import add_secret_note, delete_secret_note, get_all_secret_notes
        n = add_secret_note("To delete")
        assert delete_secret_note(n["id"]) is True
        assert get_all_secret_notes() == []

    def test_delete_nonexistent(self, mock_db_connection):
        from db.secret_notes import delete_secret_note
        assert delete_secret_note(999) is False


class TestPhysicalIsolation:
    def test_databases_are_separate(self, mock_db_connection):
        from db.secret_notes import add_secret_note, get_all_secret_notes
        add_secret_note("Secret data")
        notes = get_all_secret_notes()
        assert len(notes) == 1
