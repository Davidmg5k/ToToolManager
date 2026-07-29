from uuid import uuid4


class TestOrderList:

    def test_list_empty(self, client):
        response = client.get("/api/order/")
        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_list_with_orders(self, client, order_factory):
        order_factory(product_name="Widget", quantity=3)
        order_factory(product_name="Gadget", quantity=1)
        response = client.get("/api/order/")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 2

    def test_list_filter_by_user(self, client, user_factory, order_factory):
        user_a = user_factory(email="a@test.com")
        user_b = user_factory(email="b@test.com")
        order_factory(user=user_a, product_name="A's Order")
        order_factory(user=user_b, product_name="B's Order")
        response = client.get(f"/api/order/?user_id={user_a.user_id}")
        assert response.status_code == 200
        orders = response.json()["data"]
        assert len(orders) == 1
        assert orders[0]["product_name"] == "A's Order"


class TestOrderGet:

    def test_get_existing(self, client, order_factory):
        order = order_factory(product_name="Fetch Order", quantity=5)
        response = client.get(f"/api/order/{order.order_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["product_name"] == "Fetch Order"
        assert data["quantity"] == 5

    def test_get_nonexistent(self, client):
        fake_id = uuid4()
        response = client.get(f"/api/order/{fake_id}")
        assert response.status_code == 400
        assert "not found" in response.json()["error"].lower()


class TestOrderCreate:

    def test_create_valid(self, client, user_factory):
        user = user_factory()
        response = client.post("/api/order/", data={
            "user_id": str(user.user_id),
            "product_name": "New Order",
            "quantity": "3",
            "unit_price": "49.99",
        })
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["product_name"] == "New Order"
        assert data["quantity"] == 3
        assert data["unit_price"] == 49.99
        assert data["status"] == "pending"

    def test_create_persists(self, client, user_factory):
        user = user_factory()
        client.post("/api/order/", data={
            "user_id": str(user.user_id),
            "product_name": "Persist Order",
            "quantity": "1",
            "unit_price": "10.00",
        })
        response = client.get("/api/order/")
        orders = response.json()["data"]
        assert any(o["product_name"] == "Persist Order" for o in orders)


class TestOrderUpdate:

    def test_update_product_name(self, client, order_factory):
        order = order_factory(product_name="Old Product")
        response = client.patch(
            f"/api/order/{order.order_id}",
            json={"product_name": "New Product"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["product_name"] == "New Product"

    def test_update_quantity_and_price(self, client, order_factory):
        order = order_factory(quantity=1, unit_price=10.0)
        response = client.patch(
            f"/api/order/{order.order_id}",
            json={"quantity": 10, "unit_price": 25.50},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["quantity"] == 10
        assert data["unit_price"] == 25.50

    def test_update_status(self, client, order_factory):
        order = order_factory()
        response = client.patch(
            f"/api/order/{order.order_id}",
            json={"status": "confirmed"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "confirmed"

    def test_update_nonexistent(self, client):
        fake_id = uuid4()
        response = client.patch(
            f"/api/order/{fake_id}",
            json={"product_name": "Ghost"},
        )
        assert response.status_code == 400


class TestOrderCancel:

    def test_cancel_pending_order(self, client, order_factory):
        order = order_factory(product_name="Cancel Me")
        response = client.post(f"/api/order/{order.order_id}/cancel")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "cancelled"

    def test_cancel_nonexistent(self, client):
        fake_id = uuid4()
        response = client.post(f"/api/order/{fake_id}/cancel")
        assert response.status_code == 400


class TestOrderDelete:

    def test_delete_existing(self, client, order_factory):
        order = order_factory()
        response = client.delete(f"/api/order/{order.order_id}")
        assert response.status_code == 200
        get_resp = client.get(f"/api/order/{order.order_id}")
        assert get_resp.status_code == 400

    def test_delete_nonexistent(self, client):
        fake_id = uuid4()
        response = client.delete(f"/api/order/{fake_id}")
        assert response.status_code == 400
