"""
Personality loader — parses personalities/*.yaml files.

Each file defines an assistant persona with system_prompt, avatar emotions,
voice preset, and behavior guidelines. Similar to the skills system.

Format:
    name: "小E"
    description: "活泼可爱的女助理"
    system_prompt: |
      Your name is...
    avatar:
      default_emotion: "happy"
    voice:
      preset: "cute"
"""

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

PERSONALITIES_DIR = Path(__file__).parent.parent / "personalities"
DEFAULT_PERSONALITY = "default"


def load_personalities() -> dict[str, dict[str, Any]]:
    """Load all personality YAML files.

    Returns: dict mapping personality_id → personality dict.
        Each dict has: name, description, system_prompt, avatar, voice, wake_response
    """
    personalities: dict[str, dict[str, Any]] = {}

    if not PERSONALITIES_DIR.is_dir():
        logger.warning("Personalities directory not found: %s", PERSONALITIES_DIR)
        return personalities

    for yaml_file in sorted(PERSONALITIES_DIR.glob("*.yaml")):
        try:
            with open(yaml_file, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except Exception as exc:
            logger.warning("Skipping %s: YAML parse error: %s", yaml_file.name, exc)
            continue

        if not data or "name" not in data:
            logger.warning("Skipping %s: missing required 'name' field", yaml_file.name)
            continue

        # Derive ID from filename
        pid = yaml_file.stem  # e.g. "cute-girl" from "cute-girl.yaml"
        data["id"] = pid
        personalities[pid] = data
        logger.info("Loaded personality '%s' (%s)", data["name"], pid)

    logger.info("Loaded %d personalities from %s", len(personalities), PERSONALITIES_DIR)
    return personalities


def get_personality(personalities: dict, pid: str) -> Optional[dict[str, Any]]:
    """Get a single personality by ID."""
    return personalities.get(pid)


def save_custom_personality(data: dict[str, Any]) -> str:
    """Save custom personality to custom.yaml. Returns the file path."""
    import yaml
    path = PERSONALITIES_DIR / "custom.yaml"
    payload = {
        "name": data.get("name", "自定义助手"),
        "description": data.get("description", ""),
        "system_prompt": data.get("system_prompt", ""),
        "avatar": data.get("avatar", {"default_emotion": "idle"}),
        "voice": data.get("voice", {"preset": "default"}),
    }
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(payload, fh, allow_unicode=True, default_flow_style=False)
    logger.info("Saved custom personality to %s", path)
    return str(path)


def get_default(personalities: dict) -> dict[str, Any]:
    """Return the default personality, or a minimal fallback."""
    if DEFAULT_PERSONALITY in personalities:
        return personalities[DEFAULT_PERSONALITY]
    # Fallback: return first available, or minimal built-in
    if personalities:
        return next(iter(personalities.values()))
    return {
        "id": "fallback",
        "name": "默认助手",
        "description": "",
        "system_prompt": "你是用户的 AI 桌面助理。使用中文回复。",
        "avatar": {"default_emotion": "idle"},
        "voice": {"preset": "default"},
    }
