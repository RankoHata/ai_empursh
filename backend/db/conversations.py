"""
Conversation and turn persistence — CRUD for chat history storage.

Tables (defined in init_db.py):
  conversations:   id, title, created_at, updated_at
  conversation_turns: id, conversation_id, turn_index, user_message,
                      assistant_content, trace_json, created_at
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from .init_db import get_connection, init_db

logger = logging.getLogger(__name__)

# Ensure DB is initialized on import
init_db()


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

def create_conversation(title: str = "") -> dict:
    """Create a new conversation."""
    conn = get_connection()
    try:
        conv_id = uuid.uuid4().hex[:12]
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conv_id, title or "新对话", now, now),
        )
        conn.commit()
        logger.info("Created conversation %s: %s", conv_id, title or "新对话")
        return {"id": conv_id, "title": title or "新对话", "created_at": now, "updated_at": now}
    finally:
        conn.close()


def list_conversations() -> list[dict]:
    """Return all conversations, newest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_conversation(conv_id: str) -> Optional[dict]:
    """Get a single conversation by ID."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conv_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_conversation_title(conv_id: str, title: str) -> bool:
    """Update conversation title and timestamp."""
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        cur = conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, conv_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_conversation(conv_id: str) -> bool:
    """Delete a conversation and all its turns (CASCADE)."""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        conn.commit()
        logger.info("Deleted conversation %s", conv_id)
        return cur.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Turns
# ---------------------------------------------------------------------------

def add_turn(
    conv_id: str,
    turn_index: int,
    user_message: str,
    assistant_content: str = "",
    trace: Optional[list[dict]] = None,
) -> dict:
    """Save a completed turn to the database. Updates conversation timestamp."""
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        trace_json = json.dumps(trace or [], ensure_ascii=False)
        cur = conn.execute(
            "INSERT INTO conversation_turns "
            "(conversation_id, turn_index, user_message, assistant_content, trace_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (conv_id, turn_index, user_message, assistant_content, trace_json, now),
        )
        turn_id = cur.lastrowid

        # Touch conversation updated_at
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conv_id),
        )
        conn.commit()
        logger.debug(
            "Saved turn %s.%d: %s → %d chars (%d trace steps)",
            conv_id, turn_index, user_message[:40], len(assistant_content), len(trace or []),
        )
        return {"id": turn_id, "conversation_id": conv_id, "turn_index": turn_index}
    finally:
        conn.close()


def get_turns(conv_id: str) -> list[dict]:
    """Return all turns for a conversation, ordered by turn_index."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, conversation_id, turn_index, user_message, "
            "assistant_content, trace_json, created_at "
            "FROM conversation_turns "
            "WHERE conversation_id = ? ORDER BY turn_index",
            (conv_id,),
        ).fetchall()
        turns = []
        for r in rows:
            d = dict(r)
            d["trace"] = json.loads(d.pop("trace_json", "[]"))
            turns.append(d)
        return turns
    finally:
        conn.close()


def get_turn_count(conv_id: str) -> int:
    """Return the number of turns in a conversation."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM conversation_turns WHERE conversation_id = ?",
            (conv_id,),
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


def delete_turn(conv_id: str, turn_index: int) -> bool:
    """Delete a single turn from a conversation. Re-indexes remaining turns."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM conversation_turns WHERE conversation_id = ? AND turn_index = ?",
            (conv_id, turn_index),
        )
        conn.commit()
        if cur.rowcount > 0:
            # Re-index remaining turns (shift indices down)
            conn.execute(
                "UPDATE conversation_turns SET turn_index = turn_index - 1 "
                "WHERE conversation_id = ? AND turn_index > ?",
                (conv_id, turn_index),
            )
            conn.commit()
            logger.info("Deleted turn %s.%d", conv_id, turn_index)
            return True
        return False
    finally:
        conn.close()


def build_history_from_turns(conv_id: str) -> list[dict[str, Any]]:
    """Rebuild ChatSession-compatible message history from stored turns.

    This reconstructs the full OpenAI-compatible messages array:
      user -> assistant -> (tool_calls -> tool_results) -> assistant -> ...
    """
    turns = get_turns(conv_id)
    messages: list[dict[str, Any]] = []

    for turn in turns:
        messages.append({"role": "user", "content": turn["user_message"]})

        # Replay the trace to reconstruct intermediate tool-call messages
        trace = turn.get("trace", [])
        if trace:
            # Collect tool_call/tool_result pairs per round
            tool_calls_by_round: dict[int, list[dict]] = {}
            tool_results: dict[str, dict] = {}  # call_id -> result info

            for step in trace:
                if step["step"] == "tool_call":
                    round_num = step.get("round", 0)
                    tool_calls_by_round.setdefault(round_num, []).append({
                        "id": step["id"],
                        "type": "function",
                        "function": {
                            "name": step["name"],
                            "arguments": json.dumps(step["args"], ensure_ascii=False),
                        },
                    })
                elif step["step"] == "tool_result":
                    tool_results[step["id"]] = {
                        "role": "tool",
                        "tool_call_id": step["id"],
                        "content": json.dumps({
                            "success": step.get("success"),
                            "message": step.get("message", ""),
                            "count": step.get("count", 0),
                        }, ensure_ascii=False),
                    }

            # Reconstruct in round order: assistant[tool_calls] → tool results
            for round_num in sorted(tool_calls_by_round.keys()):
                tc_list = tool_calls_by_round[round_num]
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tc_list,
                })
                for tc in tc_list:
                    result = tool_results.get(tc["id"])
                    if result:
                        messages.append(result)

        # Final assistant response
        if turn["assistant_content"]:
            messages.append({"role": "assistant", "content": turn["assistant_content"]})

    return messages
