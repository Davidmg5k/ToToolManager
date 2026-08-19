from unittest.mock import patch, AsyncMock
from uuid import uuid4


class TestUserCRUD:

    def test_create_user(self, client):
        response = client.post("/api/user/", data={
            "user_name": "Test User",
            "email": "test_user@test.com",
            "password": "pass123",
        })
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["user_name"] == "Test User"
        assert data["email"] == "test_user@test.com"
        assert "user_id" in data

    def test_get_user(self, client, user_factory):
        user = user_factory(user_name="Fetch User", email="fetch@test.com")
        response = client.get(f"/api/user/{user.user_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["user_name"] == "Fetch User"

    def test_list_users(self, client, user_factory):
        user_factory(user_name="U1", email="u1@test.com")
        user_factory(user_name="U2", email="u2@test.com")
        response = client.get("/api/user/")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 2

    def test_update_user(self, client, user_factory):
        user = user_factory(user_name="Old", email="old@test.com")
        response = client.patch(f"/api/user/{user.user_id}", json={"user_name": "Updated"})
        assert response.status_code == 200
        assert response.json()["data"]["user_name"] == "Updated"

    def test_delete_user(self, client, user_factory):
        user = user_factory()
        response = client.delete(f"/api/user/{user.user_id}")
        assert response.status_code == 200
        get_resp = client.get(f"/api/user/{user.user_id}")
        assert get_resp.status_code == 400

    def test_get_nonexistent_user(self, client):
        response = client.get(f"/api/user/{uuid4()}")
        assert response.status_code == 400
        assert "not found" in response.json()["error"].lower()


class TestOrderCRUD:

    def test_create_order(self, client, user_factory):
        user = user_factory()
        response = client.post("/api/order/", data={
            "user_id": str(user.user_id),
            "product_name": "Test Product",
            "quantity": "2",
            "unit_price": "29.99",
        })
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["product_name"] == "Test Product"
        assert data["quantity"] == 2
        assert data["status"] == "pending"

    def test_get_order(self, client, order_factory):
        order = order_factory(product_name="Fetch Order")
        response = client.get(f"/api/order/{order.order_id}")
        assert response.status_code == 200
        assert response.json()["data"]["product_name"] == "Fetch Order"

    def test_list_orders(self, client, order_factory):
        order_factory(product_name="O1")
        order_factory(product_name="O2")
        response = client.get("/api/order/")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 2

    def test_list_orders_filter_by_user(self, client, user_factory, order_factory):
        user_a = user_factory(email="oa@test.com")
        user_b = user_factory(email="ob@test.com")
        order_factory(user=user_a, product_name="A Order")
        order_factory(user=user_b, product_name="B Order")
        response = client.get(f"/api/order/?user_id={user_a.user_id}")
        assert response.status_code == 200
        orders = response.json()["data"]
        assert len(orders) == 1
        assert orders[0]["product_name"] == "A Order"

    def test_update_order(self, client, order_factory):
        order = order_factory(product_name="Old")
        response = client.patch(f"/api/order/{order.order_id}", json={"product_name": "New"})
        assert response.status_code == 200
        assert response.json()["data"]["product_name"] == "New"

    def test_cancel_order(self, client, order_factory):
        order = order_factory()
        response = client.post(f"/api/order/{order.order_id}/cancel")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "cancelled"

    def test_delete_order(self, client, order_factory):
        order = order_factory()
        response = client.delete(f"/api/order/{order.order_id}")
        assert response.status_code == 200
        get_resp = client.get(f"/api/order/{order.order_id}")
        assert get_resp.status_code == 400


class TestInventoryCRUD:

    def test_create_product(self, client):
        response = client.post("/api/inventory/", data={
            "name": "New Product",
            "sku": "NEW-001",
            "price": "39.99",
            "stock": "100",
            "description": "A new product",
        })
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "New Product"
        assert data["sku"] == "NEW-001"
        assert data["price"] == 39.99
        assert data["stock"] == 100

    def test_get_product(self, client, product_factory):
        product = product_factory(name="Fetch Product", sku="FCH-001")
        response = client.get(f"/api/inventory/{product.product_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "Fetch Product"
        assert data["sku"] == "FCH-001"

    def test_list_products(self, client, product_factory):
        product_factory(name="P1", sku="P1-001")
        product_factory(name="P2", sku="P2-001")
        response = client.get("/api/inventory/")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 2

    def test_update_product(self, client, product_factory):
        product = product_factory(name="Old", sku="UPD-001")
        response = client.patch(f"/api/inventory/{product.product_id}", json={"name": "Updated"})
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Updated"

    def test_delete_product(self, client, product_factory):
        product = product_factory(sku="DEL-001")
        response = client.delete(f"/api/inventory/{product.product_id}")
        assert response.status_code == 200
        get_resp = client.get(f"/api/inventory/{product.product_id}")
        assert get_resp.status_code == 400

    def test_low_stock(self, client, product_factory):
        product_factory(name="Plenty", sku="LS-001", stock=50)
        product_factory(name="Low", sku="LS-002", stock=3)
        response = client.get("/api/inventory/low-stock")
        assert response.status_code == 200
        skus = [p["sku"] for p in response.json()["data"]]
        assert "LS-002" in skus
        assert "LS-001" not in skus

    def test_adjust_stock(self, client, product_factory):
        product = product_factory(stock=10)
        response = client.post("/api/inventory/adjust-stock", json={
            "product_id": str(product.product_id),
            "quantity": 5,
            "reason": "Restocking",
        })
        assert response.status_code == 200
        assert response.json()["data"]["stock"] == 15


class TestPaymentCRUD:

    def test_create_payment(self, client, order_factory):
        order = order_factory()
        response = client.post("/api/payment/", data={
            "order_id": str(order.order_id),
            "amount": "75.50",
            "method": "credit_card",
        })
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["amount"] == 75.50
        assert data["method"] == "credit_card"

    def test_get_payment(self, client, payment_factory):
        payment = payment_factory(amount=99.99)
        response = client.get(f"/api/payment/{payment.payment_id}")
        assert response.status_code == 200
        assert response.json()["data"]["amount"] == 99.99

    def test_list_payments(self, client, payment_factory):
        payment_factory(amount=10.00)
        payment_factory(amount=20.00)
        response = client.get("/api/payment/")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 2

    def test_list_payments_filter_by_order(self, client, order_factory, payment_factory):
        order_a = order_factory(product_name="Order A")
        order_b = order_factory(product_name="Order B")
        payment_factory(order=order_a, amount=10.00)
        payment_factory(order=order_b, amount=20.00)
        response = client.get(f"/api/payment/?order_id={order_a.order_id}")
        assert response.status_code == 200
        payments = response.json()["data"]
        assert len(payments) == 1
        assert payments[0]["amount"] == 10.00

    def test_update_payment(self, client, payment_factory):
        payment = payment_factory(amount=10.0)
        response = client.patch(f"/api/payment/{payment.payment_id}", json={"amount": 25.99})
        assert response.status_code == 200
        assert response.json()["data"]["amount"] == 25.99

    def test_refund_payment(self, client, order_factory):
        order = order_factory()
        create_resp = client.post("/api/payment/", data={
            "order_id": str(order.order_id),
            "amount": "50.00",
            "method": "credit_card",
        })
        payment_id = create_resp.json()["data"]["payment_id"]
        client.patch(f"/api/payment/{payment_id}", json={"status": "completed"})
        response = client.post(f"/api/payment/{payment_id}/refund")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "refunded"

    def test_delete_payment(self, client, payment_factory):
        payment = payment_factory()
        response = client.delete(f"/api/payment/{payment.payment_id}")
        assert response.status_code == 200
        get_resp = client.get(f"/api/payment/{payment.payment_id}")
        assert get_resp.status_code == 400


class TestNotificationCRUD:

    def test_create_notification(self, client, user_factory):
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

    def test_get_notification(self, client, notification_factory):
        notif = notification_factory(subject="Get Me")
        response = client.get(f"/api/notification/{notif.notification_id}")
        assert response.status_code == 200
        assert response.json()["data"]["subject"] == "Get Me"

    def test_list_notifications(self, client, notification_factory):
        notification_factory(subject="N1")
        notification_factory(subject="N2")
        response = client.get("/api/notification/")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 2

    def test_list_notifications_filter_by_user(self, client, user_factory, notification_factory):
        user_a = user_factory(email="na@test.com")
        user_b = user_factory(email="nb@test.com")
        notification_factory(user=user_a, subject="A notif")
        notification_factory(user=user_b, subject="B notif")
        response = client.get(f"/api/notification/?user_id={user_a.user_id}")
        assert response.status_code == 200
        notifs = response.json()["data"]
        assert len(notifs) == 1
        assert notifs[0]["subject"] == "A notif"

    def test_update_notification(self, client, notification_factory):
        notif = notification_factory(subject="Old")
        response = client.patch(f"/api/notification/{notif.notification_id}", json={"subject": "New"})
        assert response.status_code == 200
        assert response.json()["data"]["subject"] == "New"

    def test_resend_notification(self, client, notification_factory):
        notif = notification_factory()
        response = client.post(f"/api/notification/{notif.notification_id}/resend")
        assert response.status_code == 200

    def test_delete_notification(self, client, notification_factory):
        notif = notification_factory()
        response = client.delete(f"/api/notification/{notif.notification_id}")
        assert response.status_code == 200
        get_resp = client.get(f"/api/notification/{notif.notification_id}")
        assert get_resp.status_code == 400


class TestChatCRUD:

    def test_create_session(self, client):
        response = client.post("/api/chat/sessions", data={"title": "Test Chat"})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["title"] == "Test Chat"
        assert "chat_id" in data

    def test_create_session_default_title(self, client):
        response = client.post("/api/chat/sessions", data={})
        assert response.status_code == 200
        assert response.json()["data"]["title"] == "New Chat"

    def test_list_sessions(self, client):
        client.post("/api/chat/sessions", data={"title": "C1"})
        client.post("/api/chat/sessions", data={"title": "C2"})
        response = client.get("/api/chat/sessions")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 2

    def test_list_sessions_has_message_count(self, client):
        client.post("/api/chat/sessions", data={"title": "Count Me"})
        response = client.get("/api/chat/sessions")
        session = response.json()["data"][0]
        assert session["message_count"] == 0

    def test_update_session_title(self, client):
        create_resp = client.post("/api/chat/sessions", data={"title": "Old"})
        chat_id = create_resp.json()["data"]["chat_id"]
        response = client.patch(f"/api/chat/sessions/{chat_id}", data={"title": "New"})
        assert response.status_code == 200
        assert response.json()["data"]["title"] == "New"

    def test_update_session_empty_title(self, client):
        create_resp = client.post("/api/chat/sessions", data={"title": "Chat"})
        chat_id = create_resp.json()["data"]["chat_id"]
        response = client.patch(f"/api/chat/sessions/{chat_id}", data={"title": ""})
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

    def test_chat_status(self, client):
        create_resp = client.post("/api/chat/sessions", data={"title": "Status"})
        chat_id = create_resp.json()["data"]["chat_id"]
        response = client.get(f"/api/chat/sessions/{chat_id}/status")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "idle"

    @patch("app.router.api.chat.build_agent")
    def test_send_message_starts_task(self, mock_build_agent, client):
        mock_agent = AsyncMock()
        mock_build_agent.return_value = mock_agent
        create_resp = client.post("/api/chat/sessions", data={"title": "AI Chat"})
        chat_id = create_resp.json()["data"]["chat_id"]
        response = client.post(f"/api/chat/sessions/{chat_id}/send", data={"message": "Hello"})
        assert response.status_code == 200
        data = response.json()["data"]
        assert "task_id" in data
        assert data["status"] == "started"

    def test_send_empty_message(self, client):
        create_resp = client.post("/api/chat/sessions", data={"title": "Empty Msg"})
        chat_id = create_resp.json()["data"]["chat_id"]
        response = client.post(f"/api/chat/sessions/{chat_id}/send", data={"message": ""})
        assert response.status_code == 400
        assert "empty" in response.json()["error"].lower()


class TestAuthCRUD:

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
        assert "invalid" in response.json()["error"].lower()

    def test_login_sets_cookie(self, client, user_factory):
        user_factory(email="cookie@test.com", password="pass")
        response = client.post("/api/auth/login", data={
            "email": "cookie@test.com",
            "password": "pass",
        })
        assert "user_id" in response.cookies

    def test_logout_clears_cookie(self, client, user_factory):
        user_factory(email="logout@test.com", password="pass")
        client.post("/api/auth/login", data={
            "email": "logout@test.com",
            "password": "pass",
        })
        response = client.post("/api/auth/logout")
        assert response.status_code == 200
        assert "user_id" not in response.cookies

    def test_login_redirect_header(self, client, user_factory):
        user_factory(email="redirect@test.com", password="pass")
        response = client.post("/api/auth/login", data={
            "email": "redirect@test.com",
            "password": "pass",
        }, follow_redirects=False)
        assert response.headers.get("HX-Redirect") == "/admin/dashboard"

    def test_logout_redirect(self, client):
        response = client.post("/api/auth/logout")
        assert response.headers.get("HX-Redirect") == "/"
