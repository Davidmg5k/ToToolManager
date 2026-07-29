from uuid import uuid4


class TestUserList:

    def test_list_empty(self, client):
        response = client.get("/api/user/")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == []

    def test_list_with_users(self, client, user_factory):
        user_factory(user_name="Alice", email="alice@test.com")
        user_factory(user_name="Bob", email="bob@test.com")
        response = client.get("/api/user/")
        assert response.status_code == 200
        users = response.json()["data"]
        assert len(users) == 2

    def test_list_returns_correct_fields(self, client, user_factory):
        user_factory(user_name="Test User", email="test@test.com", password="pass123")
        response = client.get("/api/user/")
        user = response.json()["data"][0]
        assert user["user_name"] == "Test User"
        assert user["email"] == "test@test.com"
        assert "user_id" in user


class TestUserGet:

    def test_get_existing(self, client, user_factory):
        user = user_factory(user_name="Fetch Me", email="fetch@test.com")
        response = client.get(f"/api/user/{user.user_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["user_name"] == "Fetch Me"
        assert data["email"] == "fetch@test.com"

    def test_get_nonexistent(self, client):
        fake_id = uuid4()
        response = client.get(f"/api/user/{fake_id}")
        assert response.status_code == 400
        assert response.json()["success"] is False
        assert "not found" in response.json()["error"].lower()


class TestUserCreate:

    def test_create_valid(self, client):
        response = client.post("/api/user/", data={
            "user_name": "New User",
            "email": "new@test.com",
            "password": "secure123",
        })
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["user_name"] == "New User"
        assert data["email"] == "new@test.com"
        assert "user_id" in data

    def test_create_persists(self, client):
        client.post("/api/user/", data={
            "user_name": "Persist User",
            "email": "persist@test.com",
            "password": "pass",
        })
        response = client.get("/api/user/")
        users = response.json()["data"]
        assert any(u["email"] == "persist@test.com" for u in users)

    def test_create_empty_name(self, client):
        response = client.post("/api/user/", data={
            "user_name": "",
            "email": "empty@test.com",
            "password": "pass",
        })
        assert response.status_code == 201


class TestUserUpdate:

    def test_update_name(self, client, user_factory):
        user = user_factory(user_name="Old Name", email="old@test.com")
        response = client.patch(
            f"/api/user/{user.user_id}",
            json={"user_name": "New Name"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["user_name"] == "New Name"

    def test_update_email(self, client, user_factory):
        user = user_factory(email="before@test.com")
        response = client.patch(
            f"/api/user/{user.user_id}",
            json={"email": "after@test.com"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["email"] == "after@test.com"

    def test_update_nonexistent(self, client):
        fake_id = uuid4()
        response = client.patch(
            f"/api/user/{fake_id}",
            json={"user_name": "Ghost"},
        )
        assert response.status_code == 400


class TestUserDelete:

    def test_delete_existing(self, client, user_factory):
        user = user_factory(email="deleteme@test.com")
        response = client.delete(f"/api/user/{user.user_id}")
        assert response.status_code == 200

        get_resp = client.get(f"/api/user/{user.user_id}")
        assert get_resp.status_code == 400

    def test_delete_nonexistent(self, client):
        fake_id = uuid4()
        response = client.delete(f"/api/user/{fake_id}")
        assert response.status_code == 400
        assert "not found" in response.json()["error"].lower()
