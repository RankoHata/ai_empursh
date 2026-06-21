"""MCP tool schema → OpenAI function calling format adapter.

Handles:
  1. Converting MCP tools/list results to OpenAI tools schemas
  2. Tool name namespacing: mcp__<server_name>__<tool_name>
  3. Reverse lookup for call_tool routing
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Prefix applied to all MCP tools to avoid name collisions with built-in tools
MCP_PREFIX = "mcp__"
PREFIX_SEP = "__"


# ---------------------------------------------------------------------------
# Tool name helpers
# ---------------------------------------------------------------------------


def make_mcp_name(server_name: str, tool_name: str) -> str:
    """Create a namespaced tool name.

    Example:
        make_mcp_name("filesystem", "read_file") → "mcp__filesystem__read_file"
    """
    return f"{MCP_PREFIX}{server_name}{PREFIX_SEP}{tool_name}"


def parse_mcp_name(mcp_name: str) -> Optional[tuple[str, str]]:
    """Parse a namespaced tool name back to (server_name, tool_name).

    Returns None if the name is not a valid MCP namespaced name.

    Example:
        parse_mcp_name("mcp__filesystem__read_file") → ("filesystem", "read_file")
        parse_mcp_name("search_notes") → None  (built-in tool)
    """
    if not mcp_name.startswith(MCP_PREFIX):
        return None
    rest = mcp_name[len(MCP_PREFIX):]
    parts = rest.split(PREFIX_SEP, 1)
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def is_mcp_tool(name: str) -> bool:
    """Return True if the tool name is an MCP namespaced name."""
    return name.startswith(MCP_PREFIX)


# ---------------------------------------------------------------------------
# Schema conversion
# ---------------------------------------------------------------------------


def mcp_tool_to_openai(
    server_name: str,
    mcp_tool: dict[str, Any],
) -> dict[str, Any]:
    """Convert one MCP tool definition to OpenAI function calling format.

    Args:
        server_name: Name of the MCP server (for namespacing).
        mcp_tool: A single tool entry from MCP tools/list response.
                  Expected shape: {"name": str, "description": str,
                                   "inputSchema": {"type": "object", "properties": {...}}}

    Returns:
        OpenAI format: {"type": "function", "function": {"name": ..., "description": ...,
                        "parameters": {"type": "object", "properties": ..., "required": [...]}}}
    """
    original_name = mcp_tool.get("name", "unknown")
    namespaced = make_mcp_name(server_name, original_name)
    description = mcp_tool.get("description", "")
    input_schema = mcp_tool.get("inputSchema", {})

    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    # Ensure required is always a list
    if not isinstance(required, list):
        required = list(required) if required else []

    # Strip JSON-Schema fields that confuse the model (like $schema, additionalProperties)
    cleaned_properties = {}
    for key, prop in properties.items():
        if isinstance(prop, dict):
            cleaned = {}
            for k, v in prop.items():
                if not k.startswith("$"):
                    cleaned[k] = v
            cleaned_properties[key] = cleaned
        else:
            cleaned_properties[key] = prop

    logger.debug(
        "MCP tool converted: %s → %s (params: %s, required: %s)",
        original_name, namespaced, list(cleaned_properties.keys()), required,
    )

    return {
        "type": "function",
        "function": {
            "name": namespaced,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": cleaned_properties,
                "required": required,
            },
        },
    }


def mcp_tools_to_openai(
    server_name: str,
    mcp_tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert a list of MCP tool definitions to OpenAI format."""
    return [
        mcp_tool_to_openai(server_name, tool)
        for tool in mcp_tools
    ]
