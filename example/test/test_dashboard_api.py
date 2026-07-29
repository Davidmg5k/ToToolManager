class TestDashboardStats:

    def test_stats_empty_db(self, client):
        response = client.get("/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["users"] == 0
        assert data["orders"] == 0
        assert data["products"] == 0
        assert data["payments"] == 0
        assert data["recent_orders"] == []
        assert data["low_stock_products"] == []

    def test_stats_with_data(self, client, user_factory, order_factory, product_factory, payment_factory):
        user_a = user_factory(user_name="U1", email="u1@test.com")
        user_b = user_factory(user_name="U2", email="u2@test.com")
        order_a = order_factory(user=user_a, product_name="Order 1")
        order_factory(user=user_a, product_name="Order 2")
        order_factory(user=user_b, product_name="Order 3")
        product_factory(name="P1", sku="P1", stock=50)
        product_factory(name="P2", sku="P2", stock=5)
        payment_factory(order=order_a, amount=100.0)

        response = client.get("/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["users"] == 2
        assert data["orders"] == 3
        assert data["products"] == 2
        assert data["payments"] == 1

    def test_stats_recent_orders_limit(self, client, order_factory):
        for i in range(7):
            order_factory(product_name=f"Order {i}")
        response = client.get("/api/dashboard/stats")
        data = response.json()["data"]
        assert len(data["recent_orders"]) == 5

    def test_stats_low_stock_products(self, client, product_factory):
        product_factory(name="High", sku="HIGH", stock=100)
        product_factory(name="Low", sku="LOW", stock=3)
        product_factory(name="Zero", sku="ZERO", stock=0)
        response = client.get("/api/dashboard/stats")
        data = response.json()["data"]
        low_skus = [p["sku"] for p in data["low_stock_products"]]
        assert "LOW" in low_skus
        assert "ZERO" in low_skus
        assert "HIGH" not in low_skus
