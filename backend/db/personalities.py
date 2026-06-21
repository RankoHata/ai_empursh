"""
Personality CRUD — SQLite-backed personality storage.

Seed personalities are loaded from YAML files on first run,
then all operations work against the DB.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from .init_db import get_connection, init_db

logger = logging.getLogger(__name__)

init_db()

SEED_DIR = Path(__file__).parent.parent / "personalities"

# Pre-built personality IDs (for seed tracking / delete protection)
DEFAULT_PERSONALITY_ID = "default"


# ---------------------------------------------------------------------------
# Seed: load YAML files into DB on first run
# ---------------------------------------------------------------------------

def seed_personalities() -> int:
    """Import YAML personality files into DB if table is empty.

    Supports ``parent_name`` field: a symbolic reference to another personality's
    ``name``, resolved to ``parent_id`` after all records are inserted.
    This allows multi-version seed files to link without knowing auto-increment IDs.

    Returns the number of new seed personalities imported.
    """
    conn = get_connection()
    try:
        existing = conn.execute("SELECT COUNT(*) as cnt FROM personalities").fetchone()
        was_empty = not existing or existing["cnt"] == 0

        seeded = 0
        if was_empty:
            # First pass: insert all records (parent_id left NULL for parent_name refs)
            pending_links: list[tuple[int, str]] = []  # (row_id, parent_name)
            for yaml_file in sorted(SEED_DIR.glob("*.yaml")):
                try:
                    with open(yaml_file, "r", encoding="utf-8") as fh:
                        data = yaml.safe_load(fh)
                except Exception as exc:
                    logger.warning("Skipping %s: %s", yaml_file.name, exc)
                    continue
                if not data or "name" not in data:
                    continue

                parent_name = data.get("parent_name")
                parent_id = data.get("parent_id")  # explicit ID takes priority

                cur = conn.execute(
                    "INSERT INTO personalities "
                    "(name, description, system_prompt, is_seed, parent_id, version_tag, metadata) "
                    "VALUES (?, ?, ?, 1, ?, ?, ?)",
                    (
                        data.get("name", yaml_file.stem),
                        data.get("description", ""),
                        data.get("system_prompt", ""),
                        parent_id if not parent_name else None,
                        data.get("version_tag"),
                        data.get("metadata"),
                    ),
                )
                if parent_name and not parent_id:
                    pending_links.append((cur.lastrowid, parent_name))
                seeded += 1
                logger.info("Seeded personality: %s", data["name"])

            # Second pass: resolve parent_name → parent_id
            for row_id, parent_name in pending_links:
                parent_row = conn.execute(
                    "SELECT id FROM personalities WHERE name = ?", (parent_name,)
                ).fetchone()
                if parent_row:
                    conn.execute(
                        "UPDATE personalities SET parent_id = ? WHERE id = ?",
                        (parent_row["id"], row_id),
                    )
                    logger.info("  Linked '%s' (id=%d) → parent '%s' (id=%d)",
                                parent_name, row_id, parent_name, parent_row["id"])

        conn.commit()
        return seeded
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def list_personalities() -> list[dict[str, Any]]:
    """Return all personalities, seeds first then user-created."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, description, system_prompt, is_seed, "
            "parent_id, version_tag, metadata, created_at, updated_at "
            "FROM personalities ORDER BY is_seed DESC, id ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_personality(pid: int) -> Optional[dict[str, Any]]:
    """Get a single personality by DB id."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, description, system_prompt, is_seed, "
            "parent_id, version_tag, metadata, created_at, updated_at "
            "FROM personalities WHERE id = ?",
            (pid,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_personality(
    name: str,
    description: str = "",
    system_prompt: str = "",
    parent_id: Optional[int] = None,
    version_tag: Optional[str] = None,
    metadata: Optional[str] = None,
) -> dict[str, Any]:
    """Create a new user personality."""
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        cur = conn.execute(
            "INSERT INTO personalities "
            "(name, description, system_prompt, is_seed, parent_id, version_tag, metadata, created_at, updated_at) "
            "VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?)",
            (name or "未命名", description, system_prompt, parent_id, version_tag, metadata, now, now),
        )
        conn.commit()
        pid = cur.lastrowid
        logger.info("Created personality %d: %s", pid, name)
        return get_personality(pid)
    finally:
        conn.close()


def update_personality(
    pid: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    system_prompt: Optional[str] = None,
    version_tag: Optional[str] = None,
    metadata: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Update a personality. Returns updated record or None if not found."""
    conn = get_connection()
    try:
        existing = get_personality(pid)
        if not existing:
            return None
        now = datetime.now().isoformat()
        cur = conn.execute(
            "UPDATE personalities SET name=?, description=?, system_prompt=?, "
            "version_tag=?, metadata=?, updated_at=? WHERE id=?",
            (
                name if name is not None else existing["name"],
                description if description is not None else existing["description"],
                system_prompt if system_prompt is not None else existing["system_prompt"],
                version_tag if version_tag is not None else existing.get("version_tag"),
                metadata if metadata is not None else existing.get("metadata"),
                now,
                pid,
            ),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
        logger.info("Updated personality %d: %s", pid, name or existing["name"])
        return get_personality(pid)
    finally:
        conn.close()


def delete_personality(pid: int) -> bool:
    """Delete a personality. Seed personalities (is_seed=1) cannot be deleted."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT is_seed FROM personalities WHERE id=?", (pid,)).fetchone()
        if not row:
            return False
        if row["is_seed"]:
            logger.warning("Cannot delete seed personality %d", pid)
            return False
        conn.execute("DELETE FROM personalities WHERE id=?", (pid,))
        conn.commit()
        logger.info("Deleted personality %d", pid)
        return True
    finally:
        conn.close()


def get_default_personality() -> dict[str, Any]:
    """Return the first available personality, or a minimal fallback."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, description, system_prompt, is_seed, "
            "parent_id, version_tag, metadata, created_at, updated_at "
            "FROM personalities ORDER BY is_seed DESC, id ASC LIMIT 1"
        ).fetchone()
        if row:
            return dict(row)
    finally:
        conn.close()

    # Ultimate fallback
    return {
        "id": 0, "name": "默认助手", "description": "",
        "system_prompt": "你是用户的 AI 桌面助理。使用中文回复。",
        "is_seed": 0, "parent_id": None, "version_tag": None, "metadata": None,
        "created_at": "", "updated_at": "",
    }
