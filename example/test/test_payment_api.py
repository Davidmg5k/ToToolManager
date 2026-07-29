from uuid import uuid4


class TestPaymentList:

    def test_list_empty(self, client):
        response = client.get("/api/payment/")
        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_list_with_payments(self, client, payment_factory):
        payment_factory(amount=10.00)
        payment_factory(amount=20.00)
        response = client.get("/api/payment/")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 2

    def test_list_filter_by_order(self, client, order_factory, payment_factory):
        order_a = order_factory(product_name="Order A")
        order_b = order_factory(product_name="Order B")
        payment_factory(order=order_a, amount=10.00)
        payment_factory(order=order_b, amount=20.00)
        response = client.get(f"/api/payment/?order_id={order_a.order_id}")
        assert response.status_code == 200
        payments = response.json()["data"]
        assert len(payments) == 1
        assert payments[0]["amount"] == 10.00


class TestPaymentGet:

    def test_get_existing(self, client, payment_factory):
        payment = payment_factory(amount=99.99)
        response = client.get(f"/api/payment/{payment.payment_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["amount"] == 99.99

    def test_get_nonexistent(self, client):
        fake_id = uuid4()
        response = client.get(f"/api/payment/{fake_id}")
        assert response.status_code == 400
        assert "not found" in response.json()["error"].lower()


class TestPaymentCreate:

    def test_create_valid(self, client, order_factory):
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

    def test_create_with_different_method(self, client, order_factory):
        order = order_factory()
        response = client.post("/api/payment/", data={
            "order_id": str(order.order_id),
            "amount": "50.00",
            "method": "bank_transfer",
        })
        assert response.status_code == 201
        assert response.json()["data"]["method"] == "bank_transfer"


class TestPaymentUpdate:

    def test_update_status(self, client, payment_factory):
        payment = payment_factory()
        response = client.patch(
            f"/api/payment/{payment.payment_id}",
            json={"status": "completed"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "completed"

    def test_update_amount(self, client, payment_factory):
        payment = payment_factory(amount=10.0)
        response = client.patch(
            f"/api/payment/{payment.payment_id}",
            json={"amount": 25.99},
        )
        assert response.status_code == 200
        assert response.json()["data"]["amount"] == 25.99

    def test_update_nonexistent(self, client):
        fake_id = uuid4()
        response = client.patch(
            f"/api/payment/{fake_id}",
            json={"status": "failed"},
        )
        assert response.status_code == 400


class TestPaymentRefund:

    def test_refund_completed_payment(self, client, order_factory):
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

    def test_refund_nonexistent(self, client):
        fake_id = uuid4()
        response = client.post(f"/api/payment/{fake_id}/refund")
        assert response.status_code == 400


class TestPaymentDelete:

    def test_delete_existing(self, client, payment_factory):
        payment = payment_factory()
        response = client.delete(f"/api/payment/{payment.payment_id}")
        assert response.status_code == 200
        get_resp = client.get(f"/api/payment/{payment.payment_id}")
        assert get_resp.status_code == 400

    def test_delete_nonexistent(self, client):
        fake_id = uuid4()
        response = client.delete(f"/api/payment/{fake_id}")
        assert response.status_code == 400
