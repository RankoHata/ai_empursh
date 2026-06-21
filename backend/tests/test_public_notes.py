"""Unit tests for public knowledge items CRUD — uses temp-file SQLite."""

import pytest
import sqlite3
import tempfile
import os


@pytest.fixture(autouse=True)
def mock_db_connection(monkeypatch):
    """Replace get_connection with a temp-file SQLite database shared across calls."""
    import db.public_notes as mod
    import db.init_db as init_db_mod

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    def _temp_conn(scope="public"):
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

    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def sample_notes(mock_db_connection):
    from db.public_notes import add_note
    n1 = add_note("First note about Python", tags=["python", "programming"], title="Python 101")
    n2 = add_note("Second note about JavaScript", tags=["javascript"], title="JS Tips")
    n3 = add_note("Another Python tip", tags=["python"], title="Python 201")
    return [n1, n2, n3]


class TestAddNote:
    def test_add_basic_note(self, mock_db_connection):
        from db.public_notes import add_note
        note = add_note("Hello World")
        assert note["id"] == 1
        assert note["content_raw"] == "Hello World"
        assert note["content_plain"] == "Hello World"
        assert note["source_type"] == "manual"
        assert note["tags"] == []

    def test_add_with_tags(self, mock_db_connection):
        from db.public_notes import add_note
        note = add_note("Content", tags=["work", "report"])
        assert set(note["tags"]) == {"work", "report"}

    def test_add_with_title(self, mock_db_connection):
        from db.public_notes import add_note
        note = add_note("Content", title="My Title")
        assert note["title"] == "My Title"

    def test_strips_markdown_in_plain(self, mock_db_connection):
        from db.public_notes import add_note
        note = add_note("**Bold** and *italic*")
        assert "**" not in note["content_plain"]
        assert "Bold" in note["content_plain"]
        assert "**Bold**" in note["content_raw"]

    def test_duplicate_tags_deduped(self, mock_db_connection):
        from db.public_notes import add_note
        note = add_note("X", tags=["tag1", "tag1", "tag2"])
        assert len(note["tags"]) == 2


class TestGetAllNotes:
    def test_returns_newest_first(self, mock_db_connection):
        from db.public_notes import add_note, get_all_notes
        n1 = add_note("First")
        n2 = add_note("Second")
        results = get_all_notes()
        assert results[0]["id"] == n2["id"]
        assert results[1]["id"] == n1["id"]


class TestSearchNotes:
    def test_search_by_keyword(self, sample_notes):
        from db.public_notes import search_notes
        results = search_notes("Python")
        assert len(results) == 2

    def test_search_by_tag(self, sample_notes):
        from db.public_notes import search_notes
        results = search_notes("javascript")
        assert len(results) == 1
        assert results[0]["title"] == "JS Tips"

    def test_filter_by_tags(self, sample_notes):
        from db.public_notes import search_notes
        results = search_notes(tags=["python"])
        assert len(results) == 2

    def test_search_no_results(self, sample_notes):
        from db.public_notes import search_notes
        results = search_notes("nonexistent")
        assert results == []

    def test_search_empty_query_returns_all(self, sample_notes):
        from db.public_notes import search_notes
        results = search_notes()
        assert len(results) == 3


class TestDeleteNote:
    def test_delete_existing(self, mock_db_connection):
        from db.public_notes import add_note, delete_note, get_all_notes
        n = add_note("To delete")
        assert delete_note(n["id"]) is True
        assert get_all_notes() == []

    def test_delete_nonexistent(self, mock_db_connection):
        from db.public_notes import delete_note
        assert delete_note(999) is False


class TestGetAllTags:
    def test_returns_unique_tags(self, mock_db_connection):
        from db.public_notes import add_note, get_all_tags
        add_note("A", tags=["python", "work"])
        add_note("B", tags=["python", "life"])
        tags = get_all_tags()
        assert set(tags) == {"python", "work", "life"}
