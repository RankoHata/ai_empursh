"""Shared pytest fixtures for backend tests."""
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest_plugins = ("pytest_asyncio",)

# Ensure backend is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ═══════════════════════════════════════════════════════════════════════
# Temp DB isolation — 所有测试使用临时数据库，不污染生产数据
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session", autouse=True)
def _isolate_test_db():
    """全局 fixture: 所有测试使用临时 DB，session 结束后无条件清理。

    通过 TEST_DATA_DIR 环境变量覆盖 init_db.DATA_DIR，
    测试中创建的所有数据都在临时目录，测试成功或失败都自动删除。
    """
    path = tempfile.mkdtemp(prefix="test_ai_empursh_")
    os.environ["TEST_DATA_DIR"] = path

    # Reload init_db 以使用新的 DATA_DIR
    import db.init_db as init_db
    import importlib
    importlib.reload(init_db)

    # 初始化临时数据库
    init_db.init_db("public")
    init_db.init_db("secret")

    yield

    # 无条件清理
    os.environ.pop("TEST_DATA_DIR", None)
    shutil.rmtree(path, ignore_errors=True)


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
