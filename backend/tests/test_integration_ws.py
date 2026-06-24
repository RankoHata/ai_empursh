"""
WebSocket 集成测试 — 真实 FastAPI app + 真实消息流。

使用临时数据库（conftest.py 全局 _isolate_test_db fixture），
测试结束后无论成功失败都自动清理。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient，使用全局临时 DB。"""
    from main import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════
# 对话全链路
# ═══════════════════════════════════════════════════════════════════════

class TestConversationLifecycle:
    def test_create_conversation(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "create_conversation", "payload": {"title": "测试对话"}})
            data = ws.receive_json()
            assert data["type"] == "conversation_created"
            conv = data["payload"]
            assert "id" in conv, f"payload 缺少 id: {conv}"
            assert conv["title"] == "测试对话"

    def test_list_conversations(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "list_conversations", "payload": {}})
            data = ws.receive_json()
            assert data["type"] == "conversations_list"
            assert "conversations" in data["payload"]

    def test_create_then_list_includes_it(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "create_conversation", "payload": {"title": "E2E测试"}})
            created = ws.receive_json()
            conv_id = created["payload"]["id"]

            ws.send_json({"type": "list_conversations", "payload": {}})
            listed = ws.receive_json()
            ids = [c["id"] for c in listed["payload"]["conversations"]]
            assert conv_id in ids, f"新对话 {conv_id} 不在列表: {ids}"

    def test_get_personalities(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "get_personalities", "payload": {}})
            data = ws.receive_json()
            assert data["type"] == "personalities_list"
            assert "personalities" in data["payload"]
            assert "current" in data["payload"]

    def test_get_config(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "get_config", "payload": {}})
            data = ws.receive_json()
            assert data["type"] == "config"
            assert "model" in data["payload"]


# ═══════════════════════════════════════════════════════════════════════
# 笔记 CRUD
# ═══════════════════════════════════════════════════════════════════════

class TestNotesIntegration:
    def test_add_and_list_note(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "add_note", "payload": {"content": "集成测试笔记", "tags": ["test"]}})
            saved = ws.receive_json()
            assert saved["type"] == "note_saved"
            note = saved["payload"]["note"]
            assert note["content_raw"] == "集成测试笔记"

            ws.send_json({"type": "get_notes", "payload": {}})
            listed = ws.receive_json()
            assert listed["type"] == "notes_list"
            assert any(n["id"] == note["id"] for n in listed["payload"]["notes"])

    def test_search_notes(self, client):
        with client.websocket_connect("/ws") as ws:
            # Ensure at least one note exists
            ws.send_json({"type": "add_note", "payload": {"content": "搜索目标"}})
            ws.receive_json()  # consume note_saved

            ws.send_json({"type": "search_notes", "payload": {"query": "搜索"}})
            data = ws.receive_json()
            assert data["type"] == "search_results"
            assert len(data["payload"]["results"]) >= 1

    def test_delete_note(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "add_note", "payload": {"content": "待删除"}})
            saved = ws.receive_json()
            note_id = saved["payload"]["note"]["id"]

            ws.send_json({"type": "delete_note", "payload": {"note_id": note_id}})
            deleted = ws.receive_json()
            assert deleted["type"] == "note_deleted"


# ═══════════════════════════════════════════════════════════════════════
# 协议格式验证 — 防止 payload 嵌套错误（此前 BUG 根因）
# ═══════════════════════════════════════════════════════════════════════

class TestProtocolFormat:
    def test_conversation_created_payload_is_flat_object(self, client):
        """payload 就是对话对象本身，不是 { conversation: {...} }"""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "create_conversation", "payload": {"title": "格式测试"}})
            data = ws.receive_json()
            payload = data["payload"]
            assert isinstance(payload, dict)
            assert "id" in payload, "payload 必须直接包含 id（不是 payload.conversation.id）"
            assert "title" in payload
            assert "conversation" not in payload, "payload 不应嵌套 conversation"

    def test_conversations_list_payload_has_conversations_array(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "list_conversations", "payload": {}})
            data = ws.receive_json()
            assert "conversations" in data["payload"]
            assert isinstance(data["payload"]["conversations"], list)

    def test_personalities_list_payload_format(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "get_personalities", "payload": {}})
            data = ws.receive_json()
            payload = data["payload"]
            assert "personalities" in payload
            assert "current" in payload

    def test_config_payload_format(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "get_config", "payload": {}})
            data = ws.receive_json()
            assert "model" in data["payload"]
            assert "voice" in data["payload"]
