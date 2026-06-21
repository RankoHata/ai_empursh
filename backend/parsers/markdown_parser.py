"""
Markdown file parser for external workspace indexing.

Reads a .md file, extracts YAML front matter metadata, strips Markdown syntax,
and returns a structured dict suitable for insertion into knowledge_items.

Pure function — no database or network dependencies.
Reuses strip_markdown() from utils.markdown for the body text.
"""

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from utils.markdown import strip_markdown

logger = logging.getLogger(__name__)

# YAML front matter:  ---\n...\n---\n
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# First H1 heading (for title extraction)
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def parse_md(file_path: str) -> dict:
    """Parse a Markdown file and extract metadata + plain text.

    Args:
        file_path: Absolute path to a .md file.

    Returns:
        dict with keys:
            title         — extracted from front matter or first H1 or filename
            content_raw   — the full raw file content (UTF-8)
            content_plain — stripped of front matter and Markdown syntax
            tags          — list of tag strings from front matter
            hash          — SHA-256 hex digest of the raw content
            mtime         — os.path.getmtime as integer timestamp
    """
    path = Path(file_path)

    # Read file
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Cannot read %s: %s", file_path, exc)
        raise

    content_bytes = raw.encode("utf-8")

    # Extract YAML front matter
    fm: dict[str, Any] = {}
    body = raw
    fm_match = _FRONTMATTER_RE.match(raw)
    if fm_match:
        try:
            fm = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError as exc:
            logger.debug("Invalid YAML front matter in %s: %s", file_path, exc)
        body = raw[fm_match.end():]

    # Extract tags from front matter
    tags: list[str] = []
    fm_tags = fm.get("tags", [])
    if isinstance(fm_tags, list):
        tags = [str(t) for t in fm_tags if t]
    elif isinstance(fm_tags, str):
        tags = [t.strip() for t in fm_tags.split(",") if t.strip()]

    # Extract title: front matter → first H1 → filename stem
    title: str = (
        fm.get("title", "")
        or _extract_first_h1(body)
        or path.stem
    )

    # Strip Markdown from body for FTS indexing
    content_plain = strip_markdown(body)

    # Hash and mtime
    file_hash = hashlib.sha256(content_bytes).hexdigest()
    mtime = int(os.path.getmtime(str(path)))

    return {
        "title": str(title),
        "content_raw": raw,
        "content_plain": content_plain,
        "tags": tags,
        "hash": file_hash,
        "mtime": mtime,
    }


def _extract_first_h1(text: str) -> Optional[str]:
    """Return the first H1 heading text, or None."""
    m = _H1_RE.search(text)
    return m.group(1).strip() if m else None
