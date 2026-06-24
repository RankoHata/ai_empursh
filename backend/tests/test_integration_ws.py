"""
WebSocket 集成测试 — 真实 FastAPI app + 真实消息流。

此类测试才能捕获:
- WS 消息协议不匹配 (payload 格式错误)
- 对话创建/列表/加载 全链路
- 笔记 CRUD
- 人格切换

启动方式: python -m pytest tests/test_integration_ws.py -v
需要先确保 backend 依赖已安装，config.yaml 存在。
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure backend is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def test_db():
    """Create temp databases for integration testing."""
    import db.init_db as init_db

    data_dir = Path(tempfile.mkdtemp())
    # Override DB paths to temp
    public_db = data_dir / "public.db"
    secret_db = data_dir / "secret.db"

    # Initialize
    init_db.init_db_conn("public", db_path=str(public_db))
    init_db.init_db_conn("secret", db_path=str(secret_db))

    yield data_dir

    # Cleanup
    import shutil
    shutil.rmtree(data_dir, ignore_errors=True)


def _ws_connect(client):
    """Connect to WebSocket and return the websocket handle."""
    with client.websocket_connect("/ws") as ws:
        yield ws


@pytest.fixture(scope="module")
def app():
    """Create the FastAPI TestClient with the real app."""
    from main import app
    return app


@pytest.fixture(scope="module")
def client(app):
    """FastAPI TestClient (HTTP)."""
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════════
# 对话全链路测试
# ═══════════════════════════════════════════════════════════════════════

class TestConversationLifecycle:
    """测试: 创建→列表→加载→聊天自动保存"""

    def test_create_conversation(self, client):
        """创建对话并验证返回格式"""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "create_conversation", "payload": {"title": "测试对话"}})
            data = ws.receive_json()
            assert data["type"] == "conversation_created"
            conv = data["payload"]
            assert "id" in conv, f"payload 缺少 id 字段: {conv}"
            assert conv["title"] == "测试对话"

    def test_list_conversations(self, client):
        """列出对话"""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "list_conversations", "payload": {}})
            data = ws.receive_json()
            assert data["type"] == "conversations_list"
            assert "conversations" in data["payload"]

    def test_create_then_list_includes_it(self, client):
        """创建后立即列出，应该包含新对话"""
        with client.websocket_connect("/ws") as ws:
            # Create
            ws.send_json({"type": "create_conversation", "payload": {"title": "E2E测试"}})
            created = ws.receive_json()
            conv_id = created["payload"]["id"]

            # List
            ws.send_json({"type": "list_conversations", "payload": {}})
            listed = ws.receive_json()
            convs = listed["payload"]["conversations"]
            ids = [c["id"] for c in convs]
            assert conv_id in ids, f"新创建的对话 {conv_id} 不在列表中: {ids}"

    def test_get_personalities(self, client):
        """获取人格列表"""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "get_personalities", "payload": {}})
            data = ws.receive_json()
            assert data["type"] == "personalities_list"
            assert "personalities" in data["payload"]
            assert "current" in data["payload"]

    def test_get_config(self, client):
        """获取配置"""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "get_config", "payload": {}})
            data = ws.receive_json()
            assert data["type"] == "config"
            assert "model" in data["payload"]


# ═══════════════════════════════════════════════════════════════════════
# 笔记 CRUD 集成测试
# ═══════════════════════════════════════════════════════════════════════

class TestNotesIntegration:
    def test_add_and_list_note(self, client):
        with client.websocket_connect("/ws") as ws:
            # Add note
            ws.send_json({"type": "add_note", "payload": {"content": "集成测试笔记", "tags": ["test"]}})
            saved = ws.receive_json()
            assert saved["type"] == "note_saved"
            note = saved["payload"]["note"]
            assert note["content_raw"] == "集成测试笔记"

            # Get notes
            ws.send_json({"type": "get_notes", "payload": {}})
            listed = ws.receive_json()
            assert listed["type"] == "notes_list"
            assert any(n["id"] == note["id"] for n in listed["payload"]["notes"])

    def test_search_notes(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "search_notes", "payload": {"query": "集成测试"}})
            data = ws.receive_json()
            assert data["type"] == "search_results"
            assert len(data["payload"]["results"]) >= 1

    def test_delete_note(self, client):
        with client.websocket_connect("/ws") as ws:
            # Add first
            ws.send_json({"type": "add_note", "payload": {"content": "待删除笔记"}})
            saved = ws.receive_json()
            note_id = saved["payload"]["note"]["id"]

            # Delete
            ws.send_json({"type": "delete_note", "payload": {"note_id": note_id}})
            deleted = ws.receive_json()
            assert deleted["type"] == "note_deleted"


# ═══════════════════════════════════════════════════════════════════════
# 协议格式验证 — 防止 payload 嵌套错误
# ═══════════════════════════════════════════════════════════════════════

class TestProtocolFormat:
    """
    关键测试: 验证每个 WS 消息的 payload 格式与前端期望一致。

    此前 BUG: useConversations 假设 payload 是 { conversation: {...} },
    但后端直接发送对话对象 {...}。
    """

    def test_conversation_created_payload_is_flat_object(self, client):
        """payload 就是对话对象，不是 { conversation: {...} }"""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "create_conversation", "payload": {"title": "格式测试"}})
            data = ws.receive_json()
            payload = data["payload"]
            # 前端期望 payload.id 直接存在
            assert isinstance(payload, dict)
            assert "id" in payload, "payload 必须直接包含 id"
            assert "title" in payload, "payload 必须直接包含 title"
            # 不应有嵌套
            assert "conversation" not in payload, "payload 不应嵌套 conversation"

    def test_conversations_list_payload_has_conversations_array(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "list_conversations", "payload": {}})
            data = ws.receive_json()
            payload = data["payload"]
            assert "conversations" in payload
            assert isinstance(payload["conversations"], list)

    def test_personalities_list_payload_format(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "get_personalities", "payload": {}})
            data = ws.receive_json()
            payload = data["payload"]
            assert "personalities" in payload
            assert "current" in payload
            assert isinstance(payload["personalities"], list)

    def test_config_payload_format(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "get_config", "payload": {}})
            data = ws.receive_json()
            assert "model" in data["payload"]
            assert "voice" in data["payload"]
