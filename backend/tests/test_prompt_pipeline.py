"""Tests for PromptPipeline: assembly, conditions, ordering."""
import pytest

from prompt import PromptPipeline, PromptContext
from prompt.segments.emotion import emotion_segment
from prompt.segments.compact import compact_segment
from prompt.segments.time_info import time_info_segment


# ── Basic assembly ──

class TestPipelineBuild:
    def test_empty_pipeline_returns_empty(self):
        pipeline = PromptPipeline()
        result = pipeline.build(PromptContext())
        assert result == ""

    def test_single_segment(self):
        pipeline = PromptPipeline([("test", lambda ctx: "hello")])
        result = pipeline.build(PromptContext())
        assert result == "hello"

    def test_multiple_segments_joined(self):
        pipeline = PromptPipeline([
            ("a", lambda ctx: "first"),
            ("b", lambda ctx: "second"),
        ])
        result = pipeline.build(PromptContext())
        assert "first\n\nsecond" in result

    def test_none_segment_skipped(self):
        pipeline = PromptPipeline([
            ("a", lambda ctx: "first"),
            ("b", lambda ctx: None),
            ("c", lambda ctx: "third"),
        ])
        result = pipeline.build(PromptContext())
        assert "first\n\nthird" in result
        assert "None" not in result

    def test_chain_add(self):
        pipeline = (PromptPipeline()
                    .add("a", lambda ctx: "A")
                    .add("b", lambda ctx: "B"))
        result = pipeline.build(PromptContext())
        assert result == "A\n\nB"

    def test_segment_error_graceful(self, caplog):
        def broken(ctx):
            raise RuntimeError("boom")

        pipeline = PromptPipeline([("broken", broken), ("ok", lambda ctx: "still here")])
        result = pipeline.build(PromptContext())
        assert "still here" in result
        assert "boom" in caplog.text


# ── Condition segments ──

class TestConditions:
    def test_compact_disabled_skips(self):
        ctx = PromptContext(compact_enabled=False)
        result = compact_segment(ctx)
        assert result is None

    def test_compact_enabled_outputs(self):
        ctx = PromptContext(compact_enabled=True)
        result = compact_segment(ctx)
        assert result is not None
        assert "紧凑" in result

    def test_emotion_required_outputs(self):
        ctx = PromptContext(emotion_required=True)
        result = emotion_segment(ctx)
        assert result is not None
        assert "emotion" in result

    def test_emotion_disabled_skips(self):
        ctx = PromptContext(emotion_required=False)
        result = emotion_segment(ctx)
        assert result is None

    def test_time_info_disabled_skips(self):
        ctx = PromptContext(time_context_enabled=False)
        result = time_info_segment(ctx)
        assert result is None

    def test_time_info_enabled_outputs(self):
        ctx = PromptContext(time_context_enabled=True, current_time="2026-06-24 12:00")
        result = time_info_segment(ctx)
        assert result is not None
        assert "2026-06-24 12:00" in result
        assert "北京时间" in result


# ── PromptContext defaults ──

class TestPromptContext:
    def test_defaults(self):
        ctx = PromptContext()
        assert ctx.user_name == "用户"
        assert ctx.compact_enabled is False
        assert ctx.emotion_required is True

    def test_custom_values(self):
        ctx = PromptContext(user_name="张三", compact_enabled=True)
        assert ctx.user_name == "张三"
        assert ctx.compact_enabled is True

    def test_current_time_auto_populated(self):
        ctx = PromptContext()
        assert ctx.current_time is not None
        assert ":" in ctx.current_time  # contains time separator
