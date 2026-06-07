"""
Personality system — thin wrapper over db.personalities.

YAML files in personalities/ serve only as seed data for first-run DB init.
All runtime operations go through the DB.
"""

import logging

from db.personalities import (
    seed_personalities,
    list_personalities,
    get_personality,
    create_personality,
    update_personality,
    delete_personality,
    get_default_personality,
)

logger = logging.getLogger(__name__)

# Seed on first import
_loaded = False


def ensure_seeded():
    global _loaded
    if not _loaded:
        count = seed_personalities()
        if count > 0:
            logger.info("Personality seed complete: %d imported", count)
        _loaded = True


# Re-export for backward compatibility
__all__ = [
    "ensure_seeded",
    "list_personalities",
    "get_personality",
    "create_personality",
    "update_personality",
    "delete_personality",
    "get_default_personality",
]
