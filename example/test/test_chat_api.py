from unittest.mock import patch, AsyncMock
from uuid import uuid4


class TestChatSessionCRUD:

    def test_create_session(self, client):
        response = client.post("/api/chat/sessions", data={"title": "Test Chat"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "chat_id" in data["data"]
        assert data["data"]["title"] == "Test Chat"

    def test_create_session_default_title(self, client):
        response = client.post("/api/chat/sessions", data={})
        assert response.status_code == 200
        assert response.json()["data"]["title"] == "New Chat"

    def test_list_sessions_empty(self, client):
        response = client.get("/api/chat/sessions")
        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_list_sessions_with_data(self, client):
        client.post("/api/chat/sessions", data={"title": "Chat 1"})
        client.post("/api/chat/sessions", data={"title": "Chat 2"})
        response = client.get("/api/chat/sessions")
        assert response.status_code == 200
        sessions = response.json()["data"]
        assert len(sessions) == 2

    def test_list_sessions_has_message_count(self, client):
        client.post("/api/chat/sessions", data={"title": "Count Me"})
        response = client.get("/api/chat/sessions")
        session = response.json()["data"][0]
        assert "message_count" in session
        assert session["message_count"] == 0

    def test_update_session_title(self, client):
        create_resp = client.post("/api/chat/sessions", data={"title": "Old Title"})
        chat_id = create_resp.json()["data"]["chat_id"]
        response = client.patch(
            f"/api/chat/sessions/{chat_id}",
            data={"title": "New Title"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["title"] == "New Title"

    def test_update_session_empty_title(self, client):
        create_resp = client.post("/api/chat/sessions", data={"title": "Chat"})
        chat_id = create_resp.json()["data"]["chat_id"]
        response = client.patch(
            f"/api/chat/sessions/{chat_id}",
            data={"title": ""},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["error"].lower()

    def test_delete_session(self, client):
        create_resp = client.post("/api/chat/sessions", data={"title": "Delete Me"})
        chat_id = create_resp.json()["data"]["chat_id"]
        response = client.delete(f"/api/chat/sessions/{chat_id}")
        assert response.status_code == 200

        list_resp = client.get("/api/chat/sessions")
        sessions = list_resp.json()["data"]
        assert not any(s["chat_id"] == chat_id for s in sessions)

    def test_get_messages_empty(self, client):
        create_resp = client.post("/api/chat/sessions", data={"title": "Empty"})
        chat_id = create_resp.json()["data"]["chat_id"]
        response = client.get(f"/api/chat/sessions/{chat_id}/messages")
        assert response.status_code == 200
        assert response.json()["data"] == []


class TestChatSend:

    @patch("app.router.api.chat.build_agent")
    def test_send_message_starts_task(self, mock_build_agent, client):
        mock_agent = AsyncMock()
        mock_build_agent.return_value = mock_agent

        create_resp = client.post("/api/chat/sessions", data={"title": "AI Chat"})
        chat_id = create_resp.json()["data"]["chat_id"]

        response = client.post(
            f"/api/chat/sessions/{chat_id}/send",
            data={"message": "Hello AI"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "task_id" in data
        assert data["status"] == "started"

    def test_send_empty_message(self, client):
        create_resp = client.post("/api/chat/sessions", data={"title": "Empty Msg"})
        chat_id = create_resp.json()["data"]["chat_id"]

        response = client.post(
            f"/api/chat/sessions/{chat_id}/send",
            data={"message": ""},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["error"].lower()

    def test_send_whitespace_message(self, client):
        create_resp = client.post("/api/chat/sessions", data={"title": "WS Msg"})
        chat_id = create_resp.json()["data"]["chat_id"]

        response = client.post(
            f"/api/chat/sessions/{chat_id}/send",
            data={"message": "   "},
        )
        assert response.status_code == 400


class TestChatStatus:

    def test_status_idle(self, client):
        create_resp = client.post("/api/chat/sessions", data={"title": "Status"})
        chat_id = create_resp.json()["data"]["chat_id"]
        response = client.get(f"/api/chat/sessions/{chat_id}/status")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "idle"
