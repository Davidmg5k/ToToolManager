class TestMetaAPI:

    def test_get_enums(self, client):
        response = client.get("/api/meta/enums")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        enums = data["data"]
        assert "order_status" in enums
        assert "payment_method" in enums
        assert "payment_status" in enums
        assert "notification_channel" in enums
        assert "notification_status" in enums

    def test_enums_have_expected_values(self, client):
        response = client.get("/api/meta/enums")
        data = response.json()["data"]
        assert "pending" in data["order_status"]
        assert "confirmed" in data["order_status"]
        assert "shipped" in data["order_status"]
        assert "delivered" in data["order_status"]
        assert "cancelled" in data["order_status"]

    def test_payment_methods(self, client):
        response = client.get("/api/meta/enums")
        data = response.json()["data"]
        assert "credit_card" in data["payment_method"]
        assert "debit_card" in data["payment_method"]
        assert "bank_transfer" in data["payment_method"]
        assert "cash" in data["payment_method"]
