from uuid import uuid4


class TestNotificationList:

    def test_list_empty(self, client):
        response = client.get("/api/notification/")
        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_list_with_notifications(self, client, notification_factory):
        notification_factory(subject="First")
        notification_factory(subject="Second")
        response = client.get("/api/notification/")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 2

    def test_list_filter_by_user(self, client, user_factory, notification_factory):
        user_a = user_factory(email="notif_a@test.com")
        user_b = user_factory(email="notif_b@test.com")
        notification_factory(user=user_a, subject="A's notif")
        notification_factory(user=user_b, subject="B's notif")
        response = client.get(f"/api/notification/?user_id={user_a.user_id}")
        assert response.status_code == 200
        notifs = response.json()["data"]
        assert len(notifs) == 1
        assert notifs[0]["subject"] == "A's notif"


class TestNotificationGet:

    def test_get_existing(self, client, notification_factory):
        notif = notification_factory(subject="Get Me")
        response = client.get(f"/api/notification/{notif.notification_id}")
        assert response.status_code == 200
        assert response.json()["data"]["subject"] == "Get Me"

    def test_get_nonexistent(self, client):
        fake_id = uuid4()
        response = client.get(f"/api/notification/{fake_id}")
        assert response.status_code == 400
        assert "not found" in response.json()["error"].lower()


class TestNotificationCreate:

    def test_create_valid(self, client, user_factory):
        user = user_factory()
        response = client.post("/api/notification/", data={
            "user_id": str(user.user_id),
            "channel": "email",
            "subject": "Welcome!",
            "body": "Hello there.",
            "recipient": "user@test.com",
        })
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["subject"] == "Welcome!"
        assert data["channel"] == "email"

    def test_create_sms(self, client, user_factory):
        user = user_factory()
        response = client.post("/api/notification/", data={
            "user_id": str(user.user_id),
            "channel": "sms",
            "subject": "Alert",
            "body": "Your code is 1234",
            "recipient": "+1234567890",
        })
        assert response.status_code == 201
        assert response.json()["data"]["channel"] == "sms"


class TestNotificationUpdate:

    def test_update_subject(self, client, notification_factory):
        notif = notification_factory(subject="Old Subject")
        response = client.patch(
            f"/api/notification/{notif.notification_id}",
            json={"subject": "New Subject"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["subject"] == "New Subject"

    def test_update_status(self, client, notification_factory):
        notif = notification_factory()
        response = client.patch(
            f"/api/notification/{notif.notification_id}",
            json={"status": "delivered"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "delivered"

    def test_update_nonexistent(self, client):
        fake_id = uuid4()
        response = client.patch(
            f"/api/notification/{fake_id}",
            json={"subject": "Ghost"},
        )
        assert response.status_code == 400


class TestNotificationResend:

    def test_resend_existing(self, client, notification_factory):
        notif = notification_factory()
        response = client.post(f"/api/notification/{notif.notification_id}/resend")
        assert response.status_code == 200

    def test_resend_nonexistent(self, client):
        fake_id = uuid4()
        response = client.post(f"/api/notification/{fake_id}/resend")
        assert response.status_code == 400


class TestNotificationDelete:

    def test_delete_existing(self, client, notification_factory):
        notif = notification_factory()
        response = client.delete(f"/api/notification/{notif.notification_id}")
        assert response.status_code == 200
        get_resp = client.get(f"/api/notification/{notif.notification_id}")
        assert get_resp.status_code == 400

    def test_delete_nonexistent(self, client):
        fake_id = uuid4()
        response = client.delete(f"/api/notification/{fake_id}")
        assert response.status_code == 400
