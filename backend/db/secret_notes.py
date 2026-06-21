"""
Secret knowledge-items CRUD — operates on secret.db (scope="secret").

Structurally identical to public_notes.py but connects to the secret database.
IMPORTANT: This module MUST NOT import any LLM-related modules (agent.chat, openai, etc.).
The secret data path is physically isolated from the LLM pipeline.
"""

import logging
from datetime import datetime
from typing import Optional

from .init_db import get_connection, init_db
from utils.markdown import strip_markdown

logger = logging.getLogger(__name__)

# Ensure secret DB is initialized on import
init_db("secret")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def add_secret_note(
    content: str,
    tags: Optional[list[str]] = None,
    title: Optional[str] = None,
) -> dict:
    """Create a new secret note. Returns the full note dict with tags."""
    tags = tags or []
    conn = get_connection("secret")
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
        _attach_tags(conn, note_id, tags)

        conn.commit()
        logger.info("SECRET_ACCESS: action=add_secret note_id=%d", note_id)
        return _get_by_id(conn, note_id)
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to add secret note: %s", exc)
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_all_secret_notes() -> list[dict]:
    """Return all secret knowledge items (newest first)."""
    conn = get_connection("secret")
    try:
        rows = conn.execute(
            "SELECT * FROM knowledge_items ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_dict(conn, row) for row in rows]
    finally:
        conn.close()


def search_secret_notes(
    query: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> list[dict]:
    """Full-text search on secret knowledge_items via FTS5."""
    conn = get_connection("secret")
    tags = tags or []
    try:
        if query and query.strip():
            q = query.strip()
            fts_query = _build_fts_query(q)

            fts_rows = conn.execute(
                """SELECT k.* FROM items_fts f
                   JOIN knowledge_items k ON f.rowid = k.id
                   WHERE items_fts MATCH ?
                   ORDER BY rank""",
                (fts_query,),
            ).fetchall()

            tag_rows = conn.execute(
                """SELECT DISTINCT k.* FROM knowledge_items k
                   JOIN note_tag nt ON k.id = nt.note_id
                   JOIN tags t ON nt.tag_id = t.id
                   WHERE t.name LIKE ?
                   ORDER BY k.created_at DESC""",
                (f"%{q}%",),
            ).fetchall()

            seen: set[int] = set()
            merged: list[dict] = []
            for row in fts_rows + tag_rows:
                rid = row["id"]
                if rid not in seen:
                    seen.add(rid)
                    merged.append(_row_to_dict(conn, row))

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

        if tags:
            results = [
                n for n in results
                if any(t.lower() in [nt.lower() for nt in n["tags"]] for t in tags)
            ]

        logger.info(
            "SECRET_ACCESS: action=search_secret query='%s' results=%d",
            query or "", len(results),
        )
        return results
    finally:
        conn.close()


def get_all_secret_tags() -> list[str]:
    """Return all unique tag names from the secret database."""
    conn = get_connection("secret")
    try:
        rows = conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_secret_note(note_id: int) -> bool:
    """Delete a secret knowledge item by ID."""
    conn = get_connection("secret")
    try:
        cur = conn.execute("DELETE FROM knowledge_items WHERE id = ?", (note_id,))
        conn.commit()
        logger.info("SECRET_ACCESS: action=delete_secret note_id=%d deleted=%s",
                    note_id, cur.rowcount > 0)
        return cur.rowcount > 0
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to delete secret note %d: %s", note_id, exc)
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# External file operations (used by workspace sync for secret scope)
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
    """Insert or update an external file record in the secret database."""
    tags = tags or []
    conn = get_connection("secret")
    try:
        now = datetime.now().isoformat()
        existing = conn.execute(
            "SELECT id, file_hash FROM knowledge_items WHERE source_path = ?",
            (source_path,),
        ).fetchone()

        if existing is None:
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
            conn.execute(
                """UPDATE knowledge_items
                   SET title=?, content_raw=?, content_plain=?,
                       file_mtime=?, file_hash=?, updated_at=?
                   WHERE id=?""",
                (title, content_raw, content_plain,
                 file_mtime, file_hash, now, existing["id"]),
            )
            conn.execute("DELETE FROM note_tag WHERE note_id = ?", (existing["id"],))
            _attach_tags(conn, existing["id"], tags)
            conn.commit()
            return {"note": _get_by_id(conn, existing["id"]), "status": "updated"}
        else:
            return {"note": _get_by_id(conn, existing["id"]), "status": "unchanged"}
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to upsert external file %s: %s", source_path, exc)
        raise
    finally:
        conn.close()


def delete_external_by_path(source_path: str) -> bool:
    """Delete a secret knowledge item by its source_path."""
    conn = get_connection("secret")
    try:
        cur = conn.execute(
            "DELETE FROM knowledge_items WHERE source_path = ?", (source_path,)
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to delete secret external note %s: %s", source_path, exc)
        raise
    finally:
        conn.close()


def get_external_paths() -> set[str]:
    """Return the set of all source_path values for external files in secret db."""
    conn = get_connection("secret")
    try:
        rows = conn.execute(
            "SELECT source_path FROM knowledge_items WHERE source_type = 'external_file'"
        ).fetchall()
        return {r["source_path"] for r in rows}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers (identical to public_notes.py, duplicated for physical isolation)
# ---------------------------------------------------------------------------

def _row_to_dict(conn, row) -> dict:
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
    row = conn.execute(
        "SELECT * FROM knowledge_items WHERE id = ?", (note_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Secret knowledge item {note_id} not found")
    return _row_to_dict(conn, row)


def _attach_tags(conn, note_id: int, tags: list[str]) -> None:
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
    terms = query.strip().split()
    if not terms:
        return ""
    escaped = [f'"{term}"*' for term in terms]
    return " OR ".join(escaped)
