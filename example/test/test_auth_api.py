class TestAuthLogin:

    def test_login_success(self, client, user_factory):
        user_factory(user_name="Admin", email="admin@test.com", password="admin123")
        response = client.post("/api/auth/login", data={
            "email": "admin@test.com",
            "password": "admin123",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "user_id" in data["data"]

    def test_login_wrong_password(self, client, user_factory):
        user_factory(user_name="User", email="user@test.com", password="correct")
        response = client.post("/api/auth/login", data={
            "email": "user@test.com",
            "password": "wrong",
        })
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert "invalid" in data["error"].lower()

    def test_login_nonexistent_email(self, client):
        response = client.post("/api/auth/login", data={
            "email": "ghost@test.com",
            "password": "pass",
        })
        assert response.status_code == 401
        assert response.json()["success"] is False

    def test_login_sets_cookie(self, client, user_factory):
        user_factory(email="cookie@test.com", password="pass")
        response = client.post("/api/auth/login", data={
            "email": "cookie@test.com",
            "password": "pass",
        })
        assert "user_id" in response.cookies

    def test_login_redirect_header(self, client, user_factory):
        user_factory(email="redirect@test.com", password="pass")
        response = client.post("/api/auth/login", data={
            "email": "redirect@test.com",
            "password": "pass",
        }, follow_redirects=False)
        assert response.headers.get("HX-Redirect") == "/admin/dashboard"


class TestAuthLogout:

    def test_logout_clears_cookie(self, client, user_factory):
        user_factory(email="logout@test.com", password="pass")
        client.post("/api/auth/login", data={
            "email": "logout@test.com",
            "password": "pass",
        })
        response = client.post("/api/auth/logout")
        assert response.status_code == 200
        assert "user_id" not in response.cookies

    def test_logout_redirect(self, client):
        response = client.post("/api/auth/logout")
        assert response.headers.get("HX-Redirect") == "/"
