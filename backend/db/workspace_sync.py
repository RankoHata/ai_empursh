"""
External workspace sync service.

Scans configured local directories for .md files, indexes them into the
appropriate database (data.db or secret.db based on workspace scope),
and supports both full startup sync and incremental background sync.

Change detection: mtime + SHA-256 hash.
"""

import asyncio
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Optional

from .init_db import get_connection
from parsers.markdown_parser import parse_md

logger = logging.getLogger(__name__)


def sync_workspace(workspace_config: dict) -> dict:
    """Sync a single workspace directory (synchronous, for thread-pool use).

    Args:
        workspace_config: Dict with keys:
            path           — absolute path to scan
            scope          — "public" or "secret"
            enabled        — bool (if False, no-op)
            sync_interval  — int seconds (for background; ignored here)

    Returns:
        {"added": N, "updated": N, "deleted": N, "errors": [str, ...]}
    """
    if not workspace_config.get("enabled", True):
        return {"added": 0, "updated": 0, "deleted": 0, "errors": []}

    workspace_path = workspace_config["path"]
    scope = workspace_config.get("scope", "public")

    if not os.path.isdir(workspace_path):
        logger.warning("Workspace path not found: %s", workspace_path)
        return {"added": 0, "updated": 0, "deleted": 0,
                "errors": [f"Path not found: {workspace_path}"]}

    # Import the appropriate notes module
    if scope == "secret":
        from . import secret_notes as notes_mod
    else:
        from . import public_notes as notes_mod

    conn = get_connection(scope)
    stats = {"added": 0, "updated": 0, "deleted": 0, "errors": []}

    try:
        # 1. Scan directory for .md files (top-level only in v1)
        md_files: dict[str, int] = {}  # absolute_path → mtime
        try:
            for entry in os.scandir(workspace_path):
                if entry.is_file() and entry.name.lower().endswith(".md"):
                    md_files[entry.path] = int(entry.stat().st_mtime)
        except OSError as exc:
            stats["errors"].append(f"Scan error: {exc}")
            return stats

        # 2. Get existing external paths from DB
        db_paths = notes_mod.get_external_paths()

        # 3. Process each file
        for file_path, file_mtime in md_files.items():
            try:
                # Quick check: if mtime hasn't changed, skip hash computation
                existing_mtime = _get_db_mtime(conn, file_path)
                if existing_mtime is not None and existing_mtime == file_mtime:
                    # mtime unchanged — skip (fast path)
                    continue

                # Parse the Markdown file
                parsed = parse_md(file_path)

                # Upsert into appropriate DB
                result = notes_mod.upsert_external_file(
                    source_path=file_path,
                    title=parsed["title"],
                    content_raw=parsed["content_raw"],
                    content_plain=parsed["content_plain"],
                    tags=parsed["tags"],
                    file_mtime=parsed["mtime"],
                    file_hash=parsed["hash"],
                )
                status = result["status"]
                if status == "inserted":
                    stats["added"] += 1
                elif status == "updated":
                    stats["updated"] += 1
                # "unchanged" — should not happen with mtime pre-filter, but OK

            except Exception as exc:
                logger.warning("Error processing %s: %s", file_path, exc)
                stats["errors"].append(f"{file_path}: {exc}")

        # 4. Detect deleted files: in DB but not on disk
        current_paths = set(md_files.keys())
        for db_path in db_paths:
            if db_path not in current_paths and _path_in_workspace(db_path, workspace_path):
                try:
                    notes_mod.delete_external_by_path(db_path)
                    stats["deleted"] += 1
                    logger.info("Removed deleted file from index: %s", db_path)
                except Exception as exc:
                    logger.warning("Error removing %s: %s", db_path, exc)
                    stats["errors"].append(f"Delete {db_path}: {exc}")

    finally:
        conn.close()

    if stats["added"] or stats["updated"] or stats["deleted"]:
        logger.info(
            "Sync workspace [%s] %s: +%d ~%d -%d",
            scope, workspace_path,
            stats["added"], stats["updated"], stats["deleted"],
        )

    return stats


def sync_all_workspaces(workspaces: list[dict]) -> dict:
    """Synchronously sync all enabled workspaces. Returns aggregated stats."""
    aggregated = {"added": 0, "updated": 0, "deleted": 0, "errors": []}
    for ws in workspaces:
        if not ws.get("enabled", True):
            continue
        result = sync_workspace(ws)
        aggregated["added"] += result["added"]
        aggregated["updated"] += result["updated"]
        aggregated["deleted"] += result["deleted"]
        aggregated["errors"].extend(result.get("errors", []))
    return aggregated


# ---------------------------------------------------------------------------
# Async interface (for FastAPI lifespan and manual triggers)
# ---------------------------------------------------------------------------

async def async_sync_workspace(workspace_config: dict) -> dict:
    """Async wrapper — runs sync_workspace in a thread pool."""
    return await asyncio.to_thread(sync_workspace, workspace_config)


async def async_sync_all_workspaces(workspaces: list[dict]) -> dict:
    """Async wrapper — runs all syncs in thread pool."""
    results = {"added": 0, "updated": 0, "deleted": 0, "errors": []}
    # Run all syncs concurrently in thread pool
    tasks = []
    for ws in workspaces:
        if ws.get("enabled", True):
            tasks.append(async_sync_workspace(ws))
    if tasks:
        partials = await asyncio.gather(*tasks, return_exceptions=True)
        for result in partials:
            if isinstance(result, dict):
                results["added"] += result["added"]
                results["updated"] += result["updated"]
                results["deleted"] += result["deleted"]
                results["errors"].extend(result.get("errors", []))
            elif isinstance(result, Exception):
                results["errors"].append(str(result))
    return results


async def start_background_sync(workspaces: list[dict]) -> None:
    """Background task: periodically sync workspaces based on sync_interval.

    Runs forever until cancelled. Each workspace is synced independently
    on its own interval.
    """
    logger.info("Background sync started for %d workspaces", len(workspaces))
    # Track last sync time per workspace
    last_sync: dict[int, float] = {}

    try:
        while True:
            now = time.time()
            for i, ws in enumerate(workspaces):
                if not ws.get("enabled", True):
                    continue
                interval = ws.get("sync_interval", 300)
                if interval <= 0:
                    continue  # manual-only

                last = last_sync.get(i, 0)
                if now - last >= interval:
                    logger.debug("Background sync: workspace %d (%s)", i, ws.get("path", "?"))
                    try:
                        await async_sync_workspace(ws)
                    except Exception as exc:
                        logger.error("Background sync error for %s: %s", ws.get("path"), exc)
                    last_sync[i] = now

            await asyncio.sleep(15)  # Check every 15 seconds

    except asyncio.CancelledError:
        logger.info("Background sync cancelled")
        raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db_mtime(conn, file_path: str) -> Optional[int]:
    """Return the stored mtime for a file, or None."""
    row = conn.execute(
        "SELECT file_mtime FROM knowledge_items WHERE source_path = ?",
        (file_path,),
    ).fetchone()
    return row["file_mtime"] if row else None


def _path_in_workspace(file_path: str, workspace_path: str) -> bool:
    """Check if file_path is under workspace_path."""
    try:
        fp = Path(file_path).resolve()
        wp = Path(workspace_path).resolve()
        return str(fp).startswith(str(wp))
    except Exception:
        return False
