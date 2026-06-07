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
    Also ensures at least one user-editable custom slot exists.

    Returns the number of new seed personalities imported.
    """
    conn = get_connection()
    try:
        existing = conn.execute("SELECT COUNT(*) as cnt FROM personalities").fetchone()
        was_empty = not existing or existing["cnt"] == 0

        seeded = 0
        if was_empty:
            for yaml_file in sorted(SEED_DIR.glob("*.yaml")):
                try:
                    with open(yaml_file, "r", encoding="utf-8") as fh:
                        data = yaml.safe_load(fh)
                except Exception as exc:
                    logger.warning("Skipping %s: %s", yaml_file.name, exc)
                    continue
                if not data or "name" not in data:
                    continue
                conn.execute(
                    "INSERT INTO personalities (name, description, system_prompt, is_seed) "
                    "VALUES (?, ?, ?, 1)",
                    (data.get("name", yaml_file.stem), data.get("description", ""), data.get("system_prompt", "")),
                )
                seeded += 1
                logger.info("Seeded personality: %s", data["name"])

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
            "SELECT id, name, description, system_prompt, is_seed, created_at "
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
            "SELECT id, name, description, system_prompt, is_seed, created_at "
            "FROM personalities WHERE id = ?",
            (pid,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_personality(name: str, description: str = "", system_prompt: str = "") -> dict[str, Any]:
    """Create a new user personality."""
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        cur = conn.execute(
            "INSERT INTO personalities (name, description, system_prompt, is_seed, created_at, updated_at) "
            "VALUES (?, ?, ?, 0, ?, ?)",
            (name or "未命名", description, system_prompt, now, now),
        )
        conn.commit()
        pid = cur.lastrowid
        logger.info("Created personality %d: %s", pid, name)
        return get_personality(pid)
    finally:
        conn.close()


def update_personality(pid: int, name: str, description: str = "", system_prompt: str = "") -> Optional[dict[str, Any]]:
    """Update a personality. Returns updated record or None if not found."""
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        cur = conn.execute(
            "UPDATE personalities SET name=?, description=?, system_prompt=?, updated_at=? WHERE id=?",
            (name, description, system_prompt, now, pid),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
        logger.info("Updated personality %d: %s", pid, name)
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
            "SELECT id, name, description, system_prompt, is_seed, created_at "
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
        "is_seed": 0, "created_at": "",
    }
