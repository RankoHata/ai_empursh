"""
Compatibility shim — delegates to public_notes.py.

Kept for backward compatibility: main.py imports `from db import notes as notes_db`.
All function signatures remain the same; they now operate on the new
knowledge_items table in data.db via public_notes.
"""

from .public_notes import (  # noqa: F401
    add_note,
    get_all_notes,
    search_notes,
    get_all_tags,
    delete_note,
    export_notes,
)
