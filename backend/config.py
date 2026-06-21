"""
Singleton config manager for config.yaml.

Usage:
    from config import config

    # Read
    model_name = config.model["model_name"]

    # Update
    config.save({"model": {"base_url": "https://..."}})

    # Reload from disk
    config.reload()
"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config.yaml"


class AppConfig:
    """Singleton that loads, holds, and saves config.yaml."""

    _instance: "AppConfig | None" = None

    def __init__(self) -> None:
        self.model: dict[str, Any] = {}
        self.server: dict[str, Any] = {}
        self.chat: dict[str, Any] = {}
        self.voice: dict[str, Any] = {}
        self.workspaces: list[dict[str, Any]] = []
        self.user: dict[str, Any] = {}
        self.reload()

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    @classmethod
    def get(cls) -> "AppConfig":
        """Return the singleton instance, creating it on first call."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-read config.yaml and update all sections."""
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

        self.model = data.get("model", {})
        self.server = data.get("server", {})
        self.chat = data.get("chat", {})
        self.voice = data.get("voice", {})
        self.workspaces = data.get("workspaces") or []
        self.user = data.get("user", {})
        logger.debug("Config loaded from %s", CONFIG_PATH)

    def save(self, updates: dict[str, Any]) -> None:
        """Merge updates into current config, write to disk, and reload.

        Args:
            updates: Dict with top-level keys (model, server, chat, voice).
                     Only non-empty values are applied to prevent accidental clearing.
        """
        # Load current file state (in case of external changes)
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

        # Merge updates
        for section, values in updates.items():
            if section not in data:
                data[section] = {}
            if isinstance(values, dict) and isinstance(data[section], dict):
                for k, v in values.items():
                    if v is not None and v != "":
                        data[section][k] = v
            else:
                data[section] = values

        # Write
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            yaml.dump(data, fh, allow_unicode=True, default_flow_style=False)

        # Reload into memory
        self.reload()
        logger.info("Config saved and reloaded")


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

config = AppConfig.get()
