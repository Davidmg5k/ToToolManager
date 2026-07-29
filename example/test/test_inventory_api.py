from uuid import uuid4


class TestInventoryListProducts:

    def test_list_empty(self, client):
        response = client.get("/api/inventory/")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == []

    def test_list_with_products(self, client, product_factory):
        product_factory(name="Widget A", sku="WGT-001")
        product_factory(name="Widget B", sku="WGT-002")
        response = client.get("/api/inventory/")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 2

    def test_list_returns_correct_fields(self, client, product_factory):
        product_factory(name="Test Item", sku="TST-001", price=49.99, stock=25)
        response = client.get("/api/inventory/")
        item = response.json()["data"][0]
        assert item["name"] == "Test Item"
        assert item["sku"] == "TST-001"
        assert item["price"] == 49.99
        assert item["stock"] == 25
        assert "product_id" in item


class TestInventoryGetProduct:

    def test_get_existing(self, client, product_factory):
        product = product_factory(name="Gadget", sku="GDG-001")
        response = client.get(f"/api/inventory/{product.product_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "Gadget"
        assert data["sku"] == "GDG-001"

    def test_get_nonexistent(self, client):
        fake_id = uuid4()
        response = client.get(f"/api/inventory/{fake_id}")
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["error"].lower()


class TestInventoryCreateProduct:

    def test_create_valid(self, client):
        response = client.post("/api/inventory/", data={
            "name": "New Product",
            "sku": "NEW-001",
            "price": "39.99",
            "stock": "100",
            "description": "A brand new product",
        })
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "New Product"
        assert data["sku"] == "NEW-001"
        assert data["price"] == 39.99
        assert data["stock"] == 100

    def test_create_minimal_fields(self, client):
        response = client.post("/api/inventory/", data={
            "name": "Minimal",
            "sku": "MIN-001",
            "price": "0",
            "stock": "0",
        })
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "Minimal"
        assert data["description"] == ""

    def test_create_verifies_persistence(self, client):
        client.post("/api/inventory/", data={
            "name": "Persist Me",
            "sku": "PST-001",
            "price": "10.00",
            "stock": "5",
        })
        response = client.get("/api/inventory/")
        items = response.json()["data"]
        assert any(i["sku"] == "PST-001" for i in items)


class TestInventoryUpdateProduct:

    def test_update_name(self, client, product_factory):
        product = product_factory(name="Old Name", sku="UPD-001")
        response = client.patch(
            f"/api/inventory/{product.product_id}",
            json={"name": "New Name"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "New Name"

    def test_update_price_and_stock(self, client, product_factory):
        product = product_factory(price=10.0, stock=5)
        response = client.patch(
            f"/api/inventory/{product.product_id}",
            json={"price": 25.50, "stock": 100},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["price"] == 25.50
        assert data["stock"] == 100

    def test_update_nonexistent(self, client):
        fake_id = uuid4()
        response = client.patch(
            f"/api/inventory/{fake_id}",
            json={"name": "Ghost"},
        )
        assert response.status_code == 400
        assert response.json()["success"] is False


class TestInventoryDeleteProduct:

    def test_delete_existing(self, client, product_factory):
        product = product_factory(sku="DEL-001")
        response = client.delete(f"/api/inventory/{product.product_id}")
        assert response.status_code == 200

        get_response = client.get(f"/api/inventory/{product.product_id}")
        assert get_response.status_code == 400

    def test_delete_nonexistent(self, client):
        fake_id = uuid4()
        response = client.delete(f"/api/inventory/{fake_id}")
        assert response.status_code == 400
        assert "not found" in response.json()["error"].lower()


class TestInventoryLowStock:

    def test_low_stock_default_threshold(self, client, product_factory):
        product_factory(name="Plenty", sku="LS-001", stock=50)
        product_factory(name="Low Item", sku="LS-002", stock=5)
        product_factory(name="Empty", sku="LS-003", stock=0)
        response = client.get("/api/inventory/low-stock")
        assert response.status_code == 200
        data = response.json()["data"]
        skus = [p["sku"] for p in data]
        assert "LS-002" in skus
        assert "LS-003" in skus
        assert "LS-001" not in skus

    def test_low_stock_custom_threshold(self, client, product_factory):
        product_factory(name="Medium", sku="TH-001", stock=15)
        product_factory(name="Low", sku="TH-002", stock=3)
        response = client.get("/api/inventory/low-stock?threshold=10")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["sku"] == "TH-002"

    def test_low_stock_empty_result(self, client, product_factory):
        product_factory(name="High Stock", sku="HS-001", stock=100)
        response = client.get("/api/inventory/low-stock")
        assert response.status_code == 200
        assert response.json()["data"] == []


class TestInventoryAdjustStock:

    def test_add_stock(self, client, product_factory):
        product = product_factory(stock=10)
        response = client.post("/api/inventory/adjust-stock", json={
            "product_id": str(product.product_id),
            "quantity": 5,
            "reason": "Restocking",
        })
        assert response.status_code == 200
        assert response.json()["data"]["stock"] == 15

    def test_remove_stock(self, client, product_factory):
        product = product_factory(stock=10)
        response = client.post("/api/inventory/adjust-stock", json={
            "product_id": str(product.product_id),
            "quantity": -3,
            "reason": "Sold",
        })
        assert response.status_code == 200
        assert response.json()["data"]["stock"] == 7

    def test_adjust_stock_nonexistent_product(self, client):
        fake_id = uuid4()
        response = client.post("/api/inventory/adjust-stock", json={
            "product_id": str(fake_id),
            "quantity": 5,
        })
        assert response.status_code == 400
        assert "not found" in response.json()["error"].lower()
