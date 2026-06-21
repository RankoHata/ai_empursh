"""
Security guard: placeholder generation for secret data exposure prevention.

When the LLM invokes a secret-search tool, this module generates a sanitized
result that contains NO real secret data — only a count and a hint to check
the secure panel. The real data is pushed to the frontend via WebSocket,
bypassing the LLM pipeline entirely.

Invariant: functions in this module never receive or return real secret content.
"""

from typing import Optional


def build_secret_placeholder(count: int, query: str = "") -> dict:
    """Build a sanitized result dict for LLM consumption.

    Contains NO real secret data. The count is safe to reveal.

    Args:
        count: Number of matching secret records (revealed, not the data itself).
        query: The search query (optional, for better UX in the message).

    Returns:
        A dict suitable for returning as a tool result to the LLM.
        Always has data=None to prevent accidental data leakage.
    """
    if count == 0:
        msg = "未找到匹配的秘密记录。"
    elif query:
        msg = (
            f"已检索到 {count} 条秘密记录（关键词: {query}）。"
            f"详情已推送至安全面板 🔒，请勿在聊天中展示具体内容。"
        )
    else:
        msg = (
            f"已检索到 {count} 条秘密记录。"
            f"详情已推送至安全面板 🔒，请勿在聊天中展示具体内容。"
        )

    return {
        "success": True,
        "data": None,       # NEVER include real secret data
        "count": count,
        "message": msg,
    }


def sanitize_for_llm(text: str) -> str:
    """Strip any potential sensitive patterns from text before LLM exposure.

    This is a defense-in-depth measure. Currently a pass-through; can be
    extended with regex patterns for credit card numbers, API keys, etc.

    Args:
        text: Raw text that might contain sensitive data.

    Returns:
        Sanitized text safe for LLM context.
    """
    # Future: apply regex patterns for common secrets (CCN, SSN, API keys)
    # For now, the physical isolation (secret.db + hard routing) is the
    # primary defense. This function is a placeholder for additional
    # content-aware filtering if ever needed.
    return text
