"""
Skill loader — parses skills/*.md files in Claude Code skill format.

Each skill file has YAML frontmatter + Markdown body.
The frontmatter defines: name, description, command, allowed_tools.
The body is injected as the system prompt when the skill is activated.
"""

import logging
import re
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent.parent / "skills"
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def load_skills() -> dict[str, dict]:
    """Load all skill files from the skills directory.

    Returns: dict mapping command → skill_info
        skill_info = {name, description, command, allowed_tools, system_prompt}
    """
    skills: dict[str, dict] = {}

    if not SKILLS_DIR.is_dir():
        logger.warning("Skills directory not found: %s", SKILLS_DIR)
        return skills

    for md_file in sorted(SKILLS_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            logger.warning("Skipping %s: no YAML frontmatter found", md_file.name)
            continue

        try:
            meta = yaml.safe_load(m.group(1))
        except yaml.YAMLError as exc:
            logger.warning("Skipping %s: invalid YAML frontmatter: %s", md_file.name, exc)
            continue

        body = m.group(2).strip()
        command = meta.get("command", "")

        skill = {
            "name": meta.get("name", md_file.stem),
            "description": meta.get("description", ""),
            "command": command,
            "allowed_tools": meta.get("allowed_tools", []),
            "system_prompt": body,
        }

        if command:
            skills[command] = skill
            logger.info("Loaded skill '%s' (%s)", skill["name"], command)

    logger.info("Loaded %d skills from %s", len(skills), SKILLS_DIR)
    return skills
