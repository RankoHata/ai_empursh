"""
SQLite database initialization with FTS5 full-text search support.

Schema follows the project requirements spec:
  - notes: id, content, created_at, updated_at
  - tags: id, name (unique)
  - note_tag: many-to-many join
  - notes_fts: FTS5 virtual table synced via triggers
"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "notes.db"

DDL = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS note_tag (
    note_id INTEGER,
    tag_id INTEGER,
    PRIMARY KEY (note_id, tag_id),
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    content,
    content=notes,
    content_rowid=id
);

-- Triggers to keep FTS index in sync

CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, content) VALUES('delete', old.id, old.content);
    INSERT INTO notes_fts(rowid, content) VALUES (new.id, new.content);
END;
"""


def get_connection() -> sqlite3.Connection:
    """Return a connection to the notes database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> sqlite3.Connection:
    """Initialize the database schema. Idempotent — safe to call repeatedly."""
    conn = get_connection()
    conn.executescript(DDL)
    conn.commit()
    return conn


if __name__ == "__main__":
    conn = init_db()
    print(f"Database initialized at {DB_PATH}")
    conn.close()
