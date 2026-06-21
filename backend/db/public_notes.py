"""
Public knowledge-items CRUD — operates on data.db (scope="public").

All functions accept and return dicts with the knowledge_items schema:
  id, source_type, source_path, title, content_raw, content_plain,
  file_mtime, file_hash, created_at, updated_at, plus resolved tags list.
"""

import logging
from datetime import datetime
from typing import Optional

from .init_db import get_connection, init_db
from utils.markdown import strip_markdown

logger = logging.getLogger(__name__)

# Ensure public DB is initialized on import
init_db("public")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def add_note(
    content: str,
    tags: Optional[list[str]] = None,
    title: Optional[str] = None,
) -> dict:
    """Create a new manual note. Returns the full note dict with tags.

    Args:
        content: Raw Markdown or plain text content.
        tags: Optional list of tag name strings.
        title: Optional title.
    """
    tags = tags or []
    conn = get_connection("public")
    try:
        content_plain = strip_markdown(content)
        now = datetime.now().isoformat()

        cur = conn.execute(
            """INSERT INTO knowledge_items
               (source_type, title, content_raw, content_plain, created_at, updated_at)
               VALUES ('manual', ?, ?, ?, ?, ?)""",
            (title or "", content, content_plain, now, now),
        )
        note_id = cur.lastrowid

        # Attach tags
        _attach_tags(conn, note_id, tags)

        conn.commit()
        return _get_by_id(conn, note_id)
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to add note: %s", exc)
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_all_notes() -> list[dict]:
    """Return all knowledge items ordered by creation time (newest first)."""
    conn = get_connection("public")
    try:
        rows = conn.execute(
            "SELECT * FROM knowledge_items ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_dict(conn, row) for row in rows]
    finally:
        conn.close()


def get_note_by_id(note_id: int) -> dict:
    """Return a single note by ID. Raises ValueError if not found."""
    conn = get_connection("public")
    try:
        return _get_by_id(conn, note_id)
    finally:
        conn.close()


def search_notes(
    query: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> list[dict]:
    """Full-text search via FTS5 on title + content_plain, with tag filter.

    Falls back to LIKE substring search if FTS yields no results.
    """
    conn = get_connection("public")
    tags = tags or []
    try:
        if query and query.strip():
            q = query.strip()

            # FTS5 search on items_fts
            fts_query = _build_fts_query(q)
            fts_rows = conn.execute(
                """SELECT k.* FROM items_fts f
                   JOIN knowledge_items k ON f.rowid = k.id
                   WHERE items_fts MATCH ?
                   ORDER BY rank""",
                (fts_query,),
            ).fetchall()

            # Also search by tag name LIKE
            tag_rows = conn.execute(
                """SELECT DISTINCT k.* FROM knowledge_items k
                   JOIN note_tag nt ON k.id = nt.note_id
                   JOIN tags t ON nt.tag_id = t.id
                   WHERE t.name LIKE ?
                   ORDER BY k.created_at DESC""",
                (f"%{q}%",),
            ).fetchall()

            # Merge, deduplicate by id
            seen: set[int] = set()
            merged: list[dict] = []
            for row in fts_rows + tag_rows:
                rid = row["id"]
                if rid not in seen:
                    seen.add(rid)
                    merged.append(_row_to_dict(conn, row))

            # LIKE fallback on content_plain
            if not merged:
                like_rows = conn.execute(
                    """SELECT * FROM knowledge_items
                       WHERE content_plain LIKE ? OR title LIKE ?
                       ORDER BY created_at DESC""",
                    (f"%{q}%", f"%{q}%"),
                ).fetchall()
                merged = [_row_to_dict(conn, r) for r in like_rows]

            results = merged
        else:
            rows = conn.execute(
                "SELECT * FROM knowledge_items ORDER BY created_at DESC"
            ).fetchall()
            results = [_row_to_dict(conn, row) for row in rows]

        # Filter by tags if specified
        if tags:
            results = [
                n for n in results
                if any(t.lower() in [nt.lower() for nt in n["tags"]] for t in tags)
            ]

        return results
    finally:
        conn.close()


def get_all_tags() -> list[str]:
    """Return all unique tag names from the database."""
    conn = get_connection("public")
    try:
        rows = conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_note(note_id: int) -> bool:
    """Delete a knowledge item by ID. Returns True if deleted, False if not found."""
    conn = get_connection("public")
    try:
        cur = conn.execute("DELETE FROM knowledge_items WHERE id = ?", (note_id,))
        conn.commit()
        return cur.rowcount > 0
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to delete note %d: %s", note_id, exc)
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_notes(
    note_ids: list[int],
    output_dir: Optional[str] = None,
) -> str:
    """Export selected notes to a Markdown file. Returns the output file path."""
    from pathlib import Path

    conn = get_connection("public")
    try:
        placeholders = ",".join("?" for _ in note_ids)
        rows = conn.execute(
            f"SELECT * FROM knowledge_items WHERE id IN ({placeholders})",
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
                if note.get("title"):
                    f.write(f"title: {note['title']}\n")
                f.write("---\n\n")
                f.write(note["content_raw"])
                f.write("\n\n---\n\n")

        logger.info("Exported %d notes to %s", len(notes), output_path)
        return str(output_path)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Bulk insert (used by workspace sync)
# ---------------------------------------------------------------------------

def upsert_external_file(
    source_path: str,
    title: str,
    content_raw: str,
    content_plain: str,
    tags: Optional[list[str]] = None,
    file_mtime: Optional[int] = None,
    file_hash: Optional[str] = None,
) -> dict:
    """Insert or update a knowledge item representing an external .md file.

    Matched by source_path. Returns the note dict and a status string:
      'inserted' | 'updated' | 'unchanged'
    """
    tags = tags or []
    conn = get_connection("public")
    try:
        now = datetime.now().isoformat()

        existing = conn.execute(
            "SELECT id, file_hash FROM knowledge_items WHERE source_path = ?",
            (source_path,),
        ).fetchone()

        if existing is None:
            # New file
            cur = conn.execute(
                """INSERT INTO knowledge_items
                   (source_type, source_path, title, content_raw, content_plain,
                    file_mtime, file_hash, created_at, updated_at)
                   VALUES ('external_file', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source_path, title, content_raw, content_plain,
                 file_mtime, file_hash, now, now),
            )
            note_id = cur.lastrowid
            _attach_tags(conn, note_id, tags)
            conn.commit()
            return {"note": _get_by_id(conn, note_id), "status": "inserted"}

        elif existing["file_hash"] != file_hash:
            # File changed
            conn.execute(
                """UPDATE knowledge_items
                   SET title=?, content_raw=?, content_plain=?,
                       file_mtime=?, file_hash=?, updated_at=?
                   WHERE id=?""",
                (title, content_raw, content_plain,
                 file_mtime, file_hash, now, existing["id"]),
            )
            # Update tags: remove old, insert new
            conn.execute(
                "DELETE FROM note_tag WHERE note_id = ?", (existing["id"],)
            )
            _attach_tags(conn, existing["id"], tags)
            conn.commit()
            return {"note": _get_by_id(conn, existing["id"]), "status": "updated"}

        else:
            # Unchanged
            return {"note": _get_by_id(conn, existing["id"]), "status": "unchanged"}

    except Exception as exc:
        conn.rollback()
        logger.error("Failed to upsert external file %s: %s", source_path, exc)
        raise
    finally:
        conn.close()


def delete_external_by_path(source_path: str) -> bool:
    """Delete a knowledge item by its source_path (for removed files)."""
    conn = get_connection("public")
    try:
        cur = conn.execute(
            "DELETE FROM knowledge_items WHERE source_path = ?",
            (source_path,),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to delete external note %s: %s", source_path, exc)
        raise
    finally:
        conn.close()


def get_external_paths() -> set[str]:
    """Return the set of all source_path values for external files."""
    conn = get_connection("public")
    try:
        rows = conn.execute(
            "SELECT source_path FROM knowledge_items WHERE source_type = 'external_file'"
        ).fetchall()
        return {r["source_path"] for r in rows}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(conn, row) -> dict:
    """Convert a knowledge_items row to a dict with tags resolved."""
    note_id = row["id"]
    tag_rows = conn.execute(
        """SELECT t.name FROM tags t
           JOIN note_tag nt ON t.id = nt.tag_id
           WHERE nt.note_id = ?""",
        (note_id,),
    ).fetchall()
    return {
        "id": note_id,
        "source_type": row["source_type"],
        "source_path": row["source_path"],
        "title": row["title"],
        "content_raw": row["content_raw"],
        "content_plain": row["content_plain"],
        "tags": [t["name"] for t in tag_rows],
        "file_mtime": row["file_mtime"],
        "file_hash": row["file_hash"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _get_by_id(conn, note_id: int) -> dict:
    """Get a single knowledge item by ID (caller manages connection)."""
    row = conn.execute(
        "SELECT * FROM knowledge_items WHERE id = ?", (note_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Knowledge item {note_id} not found")
    return _row_to_dict(conn, row)


def _attach_tags(conn, note_id: int, tags: list[str]) -> None:
    """Insert or resolve tags and link them to a note."""
    for tag_name in tags:
        tag_name = tag_name.strip().lstrip("#")
        if not tag_name:
            continue
        conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
        row = conn.execute(
            "SELECT id FROM tags WHERE name = ?", (tag_name,)
        ).fetchone()
        if row:
            conn.execute(
                "INSERT OR IGNORE INTO note_tag (note_id, tag_id) VALUES (?, ?)",
                (note_id, row["id"]),
            )


def _build_fts_query(query: str) -> str:
    """Build an FTS5-safe query string with OR semantics and prefix matching."""
    terms = query.strip().split()
    if not terms:
        return ""
    escaped = [f'"{term}"*' for term in terms]
    return " OR ".join(escaped)


import os  # noqa: E402 — needed in export_notes
