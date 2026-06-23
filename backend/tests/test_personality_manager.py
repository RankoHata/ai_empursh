"""Tests for PersonalityManager: render_prompt, extract_emotion, reseed."""
from unittest.mock import MagicMock, patch

import pytest

from agent.personality_manager import PersonalityManager


@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.user = MagicMock()
    cfg.user.get.return_value = ""  # user_name falls back to "用户"
    return cfg


@pytest.fixture
def manager(mock_config):
    return PersonalityManager(mock_config)


# ── render_prompt ──

class TestRenderPrompt:
    def test_renders_user_name(self, manager):
        manager._config.user.get.return_value = "张三"
        personality = {"name": "测试", "system_prompt": "你好 {{ user_name }}", "version_tag": None}
        result = manager.render_prompt(personality)
        assert "你好 张三" in result

    def test_renders_current_time(self, manager):
        personality = {"name": "测试", "system_prompt": "现在时间: {{ current_time }}", "version_tag": None}
        result = manager.render_prompt(personality)
        assert "现在时间:" in result

    def test_renders_personality_name(self, manager):
        personality = {"name": "阿妮斯", "system_prompt": "我是 {{ personality_name }}", "version_tag": None}
        result = manager.render_prompt(personality)
        assert "我是 阿妮斯" in result

    def test_emotion_instruction_appended(self, manager):
        personality = {"name": "测试", "system_prompt": "你好", "version_tag": None}
        result = manager.render_prompt(personality)
        assert "emotion" in result
        assert "happy" in result
        assert "sad" in result

    def test_extra_context_merged(self, manager):
        personality = {"name": "测试", "system_prompt": "{{ extra_var }}", "version_tag": None}
        result = manager.render_prompt(personality, extra_context={"extra_var": "hello"})
        assert "hello" in result

    def test_default_user_name_when_empty(self, manager):
        manager._config.user.get.return_value = ""
        personality = {"name": "测试", "system_prompt": "{{ user_name }}", "version_tag": None}
        result = manager.render_prompt(personality)
        assert "用户" in result


# ── extract_emotion ──

class TestExtractEmotion:
    def test_bracketed_tag(self, manager):
        text = "这是回复内容\n\n[!emotion:happy!]"
        clean, emotion = manager.extract_emotion(text)
        assert clean.strip() == "这是回复内容"
        assert emotion == "happy"

    def test_unbracketed_tag(self, manager):
        """Model may drop brackets."""
        text = "这是回复内容\n\n!emotion:sad!"
        clean, emotion = manager.extract_emotion(text)
        assert "这是回复内容" in clean
        assert emotion == "sad"

    def test_no_tag_returns_idle(self, manager):
        text = "普通回复，没有标签"
        clean, emotion = manager.extract_emotion(text)
        assert clean == text
        assert emotion == "idle"

    def test_tag_with_spaces(self, manager):
        text = "[!emotion: surprised !]"
        clean, emotion = manager.extract_emotion(text)
        assert emotion == "surprised"

    def test_only_tag(self, manager):
        text = "[!emotion:thinking!]"
        clean, emotion = manager.extract_emotion(text)
        assert emotion == "thinking"
        assert clean == ""

    def test_multiple_tags_uses_first(self, manager):
        text = "[!emotion:happy!] 中间文字 [!emotion:sad!]"
        clean, emotion = manager.extract_emotion(text)
        assert emotion == "happy"

    def test_unicode_emoji_around_tag(self, manager):
        text = "好的指挥官！😊\n\n[!emotion:happy!]"
        clean, emotion = manager.extract_emotion(text)
        assert emotion == "happy"
        assert "好的指挥官" in clean


# ── reseed ──

class TestReseed:
    @patch("agent.personality_manager.personalities_db")
    def test_reseed_calls_force(self, mock_db, manager):
        mock_db.seed_personalities.return_value = 4
        count = manager.reseed()
        mock_db.seed_personalities.assert_called_once_with(force=True)
        assert count == 4
