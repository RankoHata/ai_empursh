"""
Notes tool functions — CRUD, search, and Markdown export.

All functions operate on a single SQLite database accessed via init_db.get_connection().
"""

import logging
import os
from datetime import datetime
from pathlib import Path

from .init_db import get_connection, init_db

logger = logging.getLogger(__name__)

# Ensure DB is initialized on import
init_db()


def add_note(content: str, tags: list[str] | None = None) -> dict:
    """Create a note with optional tags. Returns the full note dict."""
    tags = tags or []
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO notes (content, created_at, updated_at) VALUES (?, ?, ?)",
            (content, datetime.now().isoformat(), datetime.now().isoformat()),
        )
        note_id = cur.lastrowid

        tag_ids = []
        for tag_name in tags:
            tag_name = tag_name.strip().lstrip("#")
            if not tag_name:
                continue
            conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
            row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
            if row:
                conn.execute(
                    "INSERT OR IGNORE INTO note_tag (note_id, tag_id) VALUES (?, ?)",
                    (note_id, row["id"]),
                )
                tag_ids.append(row["id"])

        conn.commit()
        return _get_note_by_id(conn, note_id)
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to add note: %s", exc)
        raise
    finally:
        conn.close()


def get_all_notes() -> list[dict]:
    """Return all notes ordered by creation time (newest first)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, content, created_at, updated_at FROM notes ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_dict(conn, row) for row in rows]
    finally:
        conn.close()


def search_notes(query: str | None = None, tags: list[str] | None = None) -> list[dict]:
    """Full-text search via FTS5, with optional tag filter. Returns matching notes."""
    conn = get_connection()
    tags = tags or []
    try:
        if query and query.strip():
            # FTS5 search
            fts_query = _build_fts_query(query)
            rows = conn.execute(
                "SELECT n.id, n.content, n.created_at, n.updated_at "
                "FROM notes_fts f JOIN notes n ON f.rowid = n.id "
                "WHERE notes_fts MATCH ? ORDER BY rank",
                (fts_query,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, content, created_at, updated_at FROM notes ORDER BY created_at DESC"
            ).fetchall()

        results = [_row_to_dict(conn, row) for row in rows]

        # Filter by tags if specified
        if tags:
            results = [n for n in results if any(t in n["tags"] for t in tags)]

        return results
    finally:
        conn.close()


def get_all_tags() -> list[str]:
    """Return all unique tag names from the database."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()


def delete_note(note_id: int) -> bool:
    """Delete a note by ID. Returns True if deleted, False if not found."""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        return cur.rowcount > 0
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to delete note %d: %s", note_id, exc)
        raise
    finally:
        conn.close()


def export_notes(note_ids: list[int], output_dir: str | None = None) -> str:
    """Export selected notes to a Markdown file. Returns the output file path."""
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in note_ids)
        rows = conn.execute(
            f"SELECT id, content, created_at, updated_at FROM notes WHERE id IN ({placeholders})",
            note_ids,
        ).fetchall()

        notes = [_row_to_dict(conn, row) for row in rows]

        output_dir = Path(output_dir or os.path.expanduser("~/Desktop"))
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"notes_export_{timestamp}.md"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# Notes Export — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            for note in notes:
                tags_str = ", ".join(note["tags"])
                f.write("---\n")
                f.write(f"tags: [{tags_str}]\n")
                f.write(f"date: {note['created_at']}\n")
                f.write("---\n\n")
                f.write(note["content"])
                f.write("\n\n---\n\n")

        logger.info("Exported %d notes to %s", len(notes), output_path)
        return str(output_path)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(conn, row) -> dict:
    """Convert a notes row to a dict with tags included."""
    note_id = row["id"]
    tag_rows = conn.execute(
        "SELECT t.name FROM tags t "
        "JOIN note_tag nt ON t.id = nt.tag_id "
        "WHERE nt.note_id = ?",
        (note_id,),
    ).fetchall()
    return {
        "id": note_id,
        "content": row["content"],
        "tags": [t["name"] for t in tag_rows],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _get_note_by_id(conn, note_id: int) -> dict:
    """Get a single note by ID (internal — caller manages connection)."""
    row = conn.execute("SELECT id, content, created_at, updated_at FROM notes WHERE id = ?", (note_id,)).fetchone()
    if row is None:
        raise ValueError(f"Note {note_id} not found")
    return _row_to_dict(conn, row)


def _build_fts_query(query: str) -> str:
    """Build an FTS5-safe query string from user input."""
    # Escape special FTS5 characters and add prefix matching
    terms = query.strip().split()
    escaped = [f'"{term}"*' for term in terms]
    return " AND ".join(escaped)
