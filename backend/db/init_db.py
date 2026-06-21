"""
Dual-database connection factory for the knowledge base.

Provides parameterized connections to two physically separate SQLite databases:
  - data.db   (scope="public")  — public notes, conversations, personalities
  - secret.db (scope="secret")  — secret notes, never exposed to LLM

Both databases share the same knowledge_items / items_fts / tags schema.
The public database additionally stores conversation history and personalities.

Migration: detects old notes.db schema and auto-migrates to knowledge_items
           on first startup. Uses PRAGMA user_version to track state.
"""

import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database paths
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DB = DATA_DIR / "data.db"
SECRET_DB = DATA_DIR / "secret.db"
OLD_DB = DATA_DIR / "notes.db"

# ---------------------------------------------------------------------------
# DDL: Knowledge items (shared by both public and secret databases)
# ---------------------------------------------------------------------------
DDL_KNOWLEDGE = """
CREATE TABLE IF NOT EXISTS knowledge_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL CHECK(source_type IN ('manual', 'external_file')),
    source_path TEXT,
    title TEXT,
    content_raw TEXT NOT NULL,
    content_plain TEXT NOT NULL,
    file_mtime INTEGER,
    file_hash TEXT,
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
    FOREIGN KEY (note_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    title,
    content_plain,
    content=knowledge_items,
    content_rowid=id
);

-- Triggers to keep FTS index in sync with knowledge_items

CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON knowledge_items BEGIN
    INSERT INTO items_fts(rowid, title, content_plain)
    VALUES (new.id, new.title, new.content_plain);
END;

CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON knowledge_items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, content_plain)
    VALUES ('delete', old.id, old.title, old.content_plain);
END;

CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON knowledge_items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, content_plain)
    VALUES ('delete', old.id, old.title, old.content_plain);
    INSERT INTO items_fts(rowid, title, content_plain)
    VALUES (new.id, new.title, new.content_plain);
END;
"""

# Migration script: rebuild note_tag with FK pointing to knowledge_items
# (old note_tag points to notes instead)
DDL_MIGRATE_NOTE_TAG = """
DROP TABLE IF EXISTS note_tag_old;
CREATE TABLE IF NOT EXISTS note_tag_old AS SELECT * FROM note_tag;
DROP TABLE note_tag;

CREATE TABLE note_tag (
    note_id INTEGER,
    tag_id INTEGER,
    PRIMARY KEY (note_id, tag_id),
    FOREIGN KEY (note_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

INSERT OR IGNORE INTO note_tag SELECT * FROM note_tag_old;
DROP TABLE note_tag_old;
"""

# ---------------------------------------------------------------------------
# DDL: Conversation & personality schema (public database only)
# ---------------------------------------------------------------------------
DDL_CONVERSATIONS = """
CREATE TABLE IF NOT EXISTS personalities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    system_prompt TEXT NOT NULL DEFAULT '',
    is_seed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversation_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    user_message TEXT NOT NULL,
    assistant_content TEXT NOT NULL DEFAULT '',
    trace_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_turns_conv ON conversation_turns(conversation_id, turn_index);
"""

# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------

def get_connection(scope: str = "public") -> sqlite3.Connection:
    """Return a connection to the appropriate database.

    Args:
        scope: "public" → data.db,  "secret" → secret.db

    Returns:
        A sqlite3.Connection with WAL mode, foreign keys enabled, and Row factory.
    """
    db_path = SECRET_DB if scope == "secret" else DATA_DB
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def init_db(scope: str = "public") -> sqlite3.Connection:
    """Initialize the database schema. Idempotent — safe to call repeatedly.

    For the public database:
      - Handles notes.db → data.db rename (one-time migration)
      - Applies knowledge_items, conversation, and personality schemas
      - Runs data migration from old 'notes' table if needed

    For the secret database:
      - Applies only the knowledge_items schema

    Args:
        scope: "public" or "secret"
    """
    # Handle old notes.db → data.db rename (one-time, public scope only)
    if scope == "public":
        _handle_old_db_rename()

    conn = get_connection(scope)

    # Check if migration is needed BEFORE running DDL
    needs_migration = (scope == "public"
                       and _get_user_version(conn) < 1
                       and _table_exists(conn, "notes"))

    # Apply knowledge schema
    conn.executescript(DDL_KNOWLEDGE)

    # Run migration if old notes table exists
    if needs_migration:
        _run_migration(conn)

    # Conversation/personality tables only in public database
    if scope == "public":
        conn.executescript(DDL_CONVERSATIONS)

        # Migration: add personality enhancement columns (v2)
        _migrate_personality_v2(conn)

    if scope == "public" and _get_user_version(conn) < 1:
        _set_user_version(conn, 1)

    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Internal: old database migration
# ---------------------------------------------------------------------------

def _migrate_personality_v2(conn: sqlite3.Connection) -> None:
    """Add parent_id, version_tag, metadata columns to personalities table."""
    migrations = [
        "ALTER TABLE personalities ADD COLUMN parent_id INTEGER",
        "ALTER TABLE personalities ADD COLUMN version_tag TEXT",
        "ALTER TABLE personalities ADD COLUMN metadata TEXT",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists

    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_personalities_parent_id ON personalities(parent_id);
        CREATE INDEX IF NOT EXISTS idx_personalities_version_tag ON personalities(version_tag);
    """)


def _handle_old_db_rename() -> None:
    """If notes.db exists but data.db doesn't, rename notes.db → data.db."""
    if OLD_DB.exists() and not DATA_DB.exists():
        logger.info("Renaming %s → %s", OLD_DB, DATA_DB)
        os.rename(str(OLD_DB), str(DATA_DB))


def _get_user_version(conn: sqlite3.Connection) -> int:
    """Return the current PRAGMA user_version."""
    row = conn.execute("PRAGMA user_version").fetchone()
    return row[0] if row else 0


def _set_user_version(conn: sqlite3.Connection, version: int) -> None:
    """Set PRAGMA user_version."""
    conn.execute(f"PRAGMA user_version = {version}")


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check if a table exists in the database."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _run_migration(conn: sqlite3.Connection) -> None:
    """Migrate old 'notes' table to 'knowledge_items'.

    Steps:
      1. Copy notes rows → knowledge_items (preserving original IDs)
      2. Rebuild note_tag to point FK at knowledge_items instead of notes
      3. Drop old notes and notes_fts tables
    """
    logger.info("Migrating old 'notes' schema to 'knowledge_items'...")

    try:
        # Temporarily disable FK checks since we're rebuilding note_tag
        conn.execute("PRAGMA foreign_keys = OFF")

        # 1. Copy notes → knowledge_items, preserving original IDs
        old_notes = conn.execute(
            "SELECT id, content, created_at, updated_at FROM notes ORDER BY id"
        ).fetchall()

        for row in old_notes:
            conn.execute(
                """INSERT INTO knowledge_items
                   (id, source_type, content_raw, content_plain, created_at, updated_at)
                   VALUES (?, 'manual', ?, ?, ?, ?)""",
                (row["id"], row["content"], row["content"],
                 row["created_at"], row["updated_at"]),
            )
        logger.info("  Migrated %d notes to knowledge_items", len(old_notes))

        # 2. Rebuild note_tag with FK → knowledge_items
        conn.executescript(DDL_MIGRATE_NOTE_TAG)
        logger.info("  Rebuilt note_tag with FK → knowledge_items")

        # 3. Drop old tables
        conn.execute("DROP TABLE IF EXISTS notes")
        conn.execute("DROP TABLE IF EXISTS notes_fts")
        logger.info("  Dropped old 'notes' and 'notes_fts' tables")

        # Re-enable FK checks
        conn.execute("PRAGMA foreign_keys = ON")

        logger.info("Migration complete")

    except Exception as exc:
        logger.error("Migration failed: %s", exc)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass
        raise


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    conn = init_db("public")
    print(f"Public database initialized at {DATA_DB}")
    conn.close()

    conn = init_db("secret")
    print(f"Secret database initialized at {SECRET_DB}")
    conn.close()
