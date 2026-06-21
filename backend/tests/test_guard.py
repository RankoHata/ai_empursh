"""Unit tests for the security guard (placeholder generator)."""

import pytest
from security.guard import build_secret_placeholder, sanitize_for_llm


class TestBuildSecretPlaceholder:
    def test_data_is_always_none(self):
        """RED LINE: placeholder must never contain real data."""
        result = build_secret_placeholder(count=5, query="secret query")
        assert result["data"] is None

    def test_count_is_accurate(self):
        result = build_secret_placeholder(count=3)
        assert result["count"] == 3

    def test_success_is_true(self):
        result = build_secret_placeholder(count=1)
        assert result["success"] is True

    def test_message_contains_count(self):
        result = build_secret_placeholder(count=7)
        assert "7" in result["message"]

    def test_zero_count_message(self):
        result = build_secret_placeholder(count=0)
        assert "未找到" in result["message"] or "0" in result["message"]

    def test_message_includes_query_when_provided(self):
        result = build_secret_placeholder(count=2, query="银行卡")
        assert "银行卡" in result["message"]

    def test_message_has_lock_emoji(self):
        result = build_secret_placeholder(count=1)
        assert "🔒" in result["message"]

    def test_no_real_content_leakage(self):
        """Verify that the placeholder function doesn't accept or leak real data."""
        # This function only takes count and query — it has no access to real content
        result = build_secret_placeholder(count=42, query="anything")
        # The result should only contain the count and the query string
        result_str = str(result)
        assert "42" in result_str
        assert result["data"] is None


class TestSanitizeForLlm:
    def test_passthrough(self):
        """Current implementation is a pass-through."""
        assert sanitize_for_llm("hello") == "hello"

    def test_passthrough_markdown(self):
        assert sanitize_for_llm("**bold**") == "**bold**"
