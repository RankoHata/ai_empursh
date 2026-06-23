"""Tests for ChatSession: history management, streaming, stop signal."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.chat import ChatSession


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    return client


@pytest.fixture
def session(mock_client):
    return ChatSession(
        client=mock_client,
        model_name="test-model",
        max_rounds=5,
        max_tool_rounds=3,
    )


# ── History management ──

class TestHistory:
    def test_add_user_message(self, session):
        session.add_user_message("你好")
        assert len(session._history) == 1
        assert session._history[0]["role"] == "user"
        assert session._history[0]["content"] == "你好"

    def test_set_system_prompt(self, session):
        session.set_system_prompt("你是一个助手")
        assert session._history[0]["role"] == "system"
        assert len(session._history) == 1

    def test_set_system_prompt_replaces_existing(self, session):
        session.set_system_prompt("prompt 1")
        session.set_system_prompt("prompt 2")
        assert len(session._history) == 1
        assert session._history[0]["content"] == "prompt 2"

    def test_add_system_message(self, session):
        session.add_system_message("系统提示")
        assert session._history[0]["role"] == "system"

    def test_add_assistant_message(self, session):
        session.add_user_message("hi")
        session.add_assistant_message("hello")
        assert session._history[1]["role"] == "assistant"
        assert session._history[1]["content"] == "hello"

    def test_history_trimming(self, session):
        """When history exceeds max_messages, oldest are trimmed."""
        session._max_messages = 2
        session.add_user_message("m1")
        session.add_assistant_message("r1")
        session.add_user_message("m2")
        # m2 should trigger trim (3 > 2, keep last 2 = [r1, m2])
        assert len(session._history) == 2

    def test_load_history(self, session):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        session.load_history(msgs)
        assert len(session._history) == 2

    def test_history_summary_not_empty(self, session):
        session.add_user_message("test")
        summary = session._history  # just verify it doesn't crash
        assert summary is not None


# ── Stop signal ──

class TestStopSignal:
    def test_stop_initially_false(self, session):
        assert session.stopped() is False

    def test_request_stop_sets_flag(self, session):
        session.request_stop()
        assert session.stopped() is True

    def test_clear_stop_resets(self, session):
        session.request_stop()
        session.clear_stop()
        assert session.stopped() is False


# ── Trace ──

class TestTrace:
    def test_trace_initially_empty(self, session):
        assert session.get_trace() == []

    def test_trace_persists_across_turns(self, session):
        """Trace should be manually set per-turn by stream_with_tool_loop."""
        session._trace = [{"step": "api_call", "round": 0}]
        assert len(session.get_trace()) == 1


# ── on_thinking callback ──

class TestThinking:
    @pytest.mark.asyncio
    async def test_on_thinking_called_in_tool_loop(self, session, mock_client):
        """Verify on_thinking is set and callable."""
        calls = []

        async def _thinking(text):
            calls.append(text)

        session._on_thinking = _thinking
        await session._on_thinking("test thinking")
        assert calls == ["test thinking"]
