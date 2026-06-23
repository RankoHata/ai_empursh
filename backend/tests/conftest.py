"""Shared pytest fixtures for backend tests."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest_plugins = ("pytest_asyncio",)

# Ensure backend is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database and clean up after test."""
    import sqlite3
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
    os.unlink(path)


@pytest.fixture
def mock_ws():
    """Return a mock WebSocket with async send_json."""
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture
def mock_openai_client():
    """Return a mock AsyncOpenAI client."""
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    return client


@pytest.fixture
def sample_personality():
    """Return a minimal personality dict."""
    return {
        "id": 1,
        "name": "测试助手",
        "description": "测试用",
        "system_prompt": "你是 {{ user_name }} 的 AI 助理。当前时间：{{ current_time }}",
        "version_tag": None,
        "is_seed": 1,
    }
