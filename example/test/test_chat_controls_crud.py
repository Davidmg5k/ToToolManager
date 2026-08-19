import asyncio
from uuid import uuid4

import pytest
from sqlmodel import Session

from app.controller.agent import (
    build_user_service,
    build_commerce_module,
    build_communication_module,
)
from to_tool_manager import ToToolManager


@pytest.fixture(name="manager")
def manager_fixture(engine):
    session = Session(engine)
    mgr = ToToolManager([
        build_user_service(session),
        build_commerce_module(session),
        build_communication_module(session),
    ])
    yield mgr
    session.close()


def _find_spec(manager, service_name: str):
    for spec in manager.tool_specs:
        if spec.name == service_name:
            return spec
    raise ValueError(f"ToolSpec for '{service_name}' not found")


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    return obj


class TestChatCreateUserViaTools:

    def test_create_maria_paula(self, manager):
        """Simula: 'Crea al usuario Maria Paula con mapa@ttm.com y cualquier contraseña'"""
        user_spec = _find_spec(manager, "user_service")
        result = _run(user_spec.call(operations=[
            {
                "method": "create_user",
                "args": {
                    "data": {
                        "user_name": "Maria Paula",
                        "email": "mapa@ttm.com",
                        "password": "pass123",
                    }
                },
            }
        ]))
        assert result.error is None
        op = result.content[0]
        assert op["success"] is True
        user = _to_dict(op["result"])
        assert user["user_name"] == "Maria Paula"
        assert user["email"] == "mapa@ttm.com"
        assert "user_id" in user

    def test_create_user_and_verify_in_list(self, manager):
        """Crea un usuario y luego lista para confirmar que existe."""
        user_spec = _find_spec(manager, "user_service")
        _run(user_spec.call(operations=[
            {
                "method": "create_user",
                "args": {
                    "data": {
                        "user_name": "Carlos",
                        "email": "carlos@ttm.com",
                        "password": "pass123",
                    }
                },
            }
        ]))
        result = _run(user_spec.call(operations=[
            {"method": "list_users", "args": {}}
        ]))
        assert result.error is None
        users = _to_dict(result.content[0]["result"])
        assert any(u["email"] == "carlos@ttm.com" for u in users)

    def test_create_user_and_get_by_id(self, manager):
        """Crea un usuario y lo recupera por ID."""
        user_spec = _find_spec(manager, "user_service")
        create_result = _run(user_spec.call(operations=[
            {
                "method": "create_user",
                "args": {
                    "data": {
                        "user_name": "Laura",
                        "email": "laura@ttm.com",
                        "password": "secret",
                    }
                },
            }
        ]))
        user = _to_dict(create_result.content[0]["result"])
        get_result = _run(user_spec.call(operations=[
            {"method": "get_user", "args": {"data": {"user_id": user["user_id"]}}}
        ]))
        assert get_result.content[0]["success"] is True
        assert _to_dict(get_result.content[0]["result"])["user_name"] == "Laura"

    def test_create_update_delete_user_flow(self, manager):
        """Flujo completo: crear, actualizar, verificar, eliminar."""
        user_spec = _find_spec(manager, "user_service")

        create_res = _run(user_spec.call(operations=[
            {
                "method": "create_user",
                "args": {
                    "data": {
                        "user_name": "Temp User",
                        "email": "temp@ttm.com",
                        "password": "pass",
                    }
                },
            }
        ]))
        user = _to_dict(create_res.content[0]["result"])

        _run(user_spec.call(operations=[
            {"method": "update_user", "args": {"user_id": user["user_id"], "data": {"user_name": "Updated User"}}}
        ]))

        get_res = _run(user_spec.call(operations=[
            {"method": "get_user", "args": {"data": {"user_id": user["user_id"]}}}
        ]))
        assert _to_dict(get_res.content[0]["result"])["user_name"] == "Updated User"

        _run(user_spec.call(operations=[
            {"method": "delete_user", "args": {"data": {"user_id": user["user_id"]}}}
        ]))

        get_after_del = _run(user_spec.call(operations=[
            {"method": "get_user", "args": {"data": {"user_id": user["user_id"]}}}
        ]))
        assert get_after_del.content[0]["success"] is False


class TestChatBatchOperationsViaTools:

    def test_create_multiple_users_in_one_call(self, manager):
        """Batch: crear varios usuarios en una sola llamada tool."""
        user_spec = _find_spec(manager, "user_service")
        result = _run(user_spec.call(operations=[
            {
                "method": "create_user",
                "args": {"data": {"user_name": "User A", "email": "a@ttm.com", "password": "pass"}},
            },
            {
                "method": "create_user",
                "args": {"data": {"user_name": "User B", "email": "b@ttm.com", "password": "pass"}},
            },
            {
                "method": "create_user",
                "args": {"data": {"user_name": "User C", "email": "c@ttm.com", "password": "pass"}},
            },
        ]))
        assert result.error is None
        assert len(result.content) == 3
        assert all(op["success"] for op in result.content)

    def test_create_user_and_list_in_batch(self, manager):
        """Batch: crear usuario y luego listar en la misma llamada."""
        user_spec = _find_spec(manager, "user_service")
        result = _run(user_spec.call(operations=[
            {
                "method": "create_user",
                "args": {"data": {"user_name": "Batch User", "email": "batch@ttm.com", "password": "pass"}},
            },
            {"method": "list_users", "args": {}},
        ]))
        assert result.error is None
        assert result.content[0]["success"] is True
        assert result.content[1]["success"] is True
        users = _to_dict(result.content[1]["result"])
        assert any(u["email"] == "batch@ttm.com" for u in users)


class TestChatCreateOrderViaTools:

    def test_create_order_for_user(self, manager, user_factory):
        """Simula: 'Crea un pedido de 3 widgets para el usuario X'"""
        user = user_factory(user_name="Buyer", email="buyer@ttm.com")
        order_spec = _find_spec(manager, "commerce")
        result = _run(order_spec.call(operations=[
            {
                "method": "create_order",
                "args": {
                    "data": {
                        "user_id": str(user.user_id),
                        "product_name": "Widget",
                        "quantity": 3,
                        "unit_price": 29.99,
                    }
                },
            }
        ]))
        assert result.error is None
        op = result.content[0]
        assert op["success"] is True
        order = _to_dict(op["result"])
        assert order["product_name"] == "Widget"
        assert order["quantity"] == 3
        assert order["status"] == "pending"

    def test_create_order_and_cancel(self, manager, user_factory):
        """Crea un pedido y lo cancela."""
        user = user_factory(email="cancel@ttm.com")
        order_spec = _find_spec(manager, "commerce")
        create_res = _run(order_spec.call(operations=[
            {
                "method": "create_order",
                "args": {
                    "data": {
                        "user_id": str(user.user_id),
                        "product_name": "Gadget",
                        "quantity": 1,
                        "unit_price": 99.99,
                    }
                },
            }
        ]))
        order = _to_dict(create_res.content[0]["result"])

        cancel_res = _run(order_spec.call(operations=[
            {"method": "cancel_order", "args": {"data": {"order_id": order["order_id"]}}}
        ]))
        assert cancel_res.content[0]["success"] is True
        assert _to_dict(cancel_res.content[0]["result"])["status"] == "cancelled"


class TestChatCreateProductViaTools:

    def test_create_product(self, manager):
        """Simula: 'Agrega un producto Laptop HP por $999 con 10 en stock'"""
        inv_spec = _find_spec(manager, "commerce")
        result = _run(inv_spec.call(operations=[
            {
                "method": "create_product",
                "args": {
                    "data": {
                        "name": "Laptop HP",
                        "sku": "LAP-HP-001",
                        "price": 999.00,
                        "stock": 10,
                        "description": "Laptop HP 15 pulgadas",
                    }
                },
            }
        ]))
        assert result.error is None
        op = result.content[0]
        assert op["success"] is True
        product = _to_dict(op["result"])
        assert product["name"] == "Laptop HP"
        assert product["price"] == 999.00
        assert product["stock"] == 10

    def test_create_product_and_adjust_stock(self, manager):
        """Crea un producto y ajusta el stock."""
        inv_spec = _find_spec(manager, "commerce")
        create_res = _run(inv_spec.call(operations=[
            {
                "method": "create_product",
                "args": {
                    "data": {
                        "name": "Mouse",
                        "sku": "MOU-001",
                        "price": 25.00,
                        "stock": 50,
                    }
                },
            }
        ]))
        product = _to_dict(create_res.content[0]["result"])

        adjust_res = _run(inv_spec.call(operations=[
            {
                "method": "adjust_stock",
                "args": {
                    "data": {
                        "product_id": product["product_id"],
                        "quantity": -20,
                        "reason": "Ventas",
                    }
                },
            }
        ]))
        assert adjust_res.content[0]["success"] is True
        assert _to_dict(adjust_res.content[0]["result"])["stock"] == 30


class TestChatCreatePaymentViaTools:

    def test_create_payment(self, manager, user_factory):
        """Simula: 'Procesa un pago de $150 por tarjeta de crédito para el pedido X'"""
        user = user_factory(email="payer@ttm.com")
        order_spec = _find_spec(manager, "commerce")
        order_res = _run(order_spec.call(operations=[
            {
                "method": "create_order",
                "args": {
                    "data": {
                        "user_id": str(user.user_id),
                        "product_name": "Service",
                        "quantity": 1,
                        "unit_price": 150.00,
                    }
                },
            }
        ]))
        order = _to_dict(order_res.content[0]["result"])

        pay_spec = _find_spec(manager, "commerce")
        result = _run(pay_spec.call(operations=[
            {
                "method": "create_payment",
                "args": {
                    "data": {
                        "order_id": order["order_id"],
                        "amount": 150.00,
                        "method": "credit_card",
                    }
                },
            }
        ]))
        assert result.error is None
        op = result.content[0]
        assert op["success"] is True
        payment = _to_dict(op["result"])
        assert payment["amount"] == 150.00
        assert payment["status"] == "completed"


class TestChatSendNotificationViaTools:

    def test_send_notification(self, manager, user_factory):
        """Simula: 'Envía un email de bienvenida al usuario X'"""
        user = user_factory(user_name="Notif User", email="notif@ttm.com")
        comm_spec = _find_spec(manager, "communication")
        result = _run(comm_spec.call(operations=[
            {
                "method": "create_notification",
                "args": {
                    "data": {
                        "user_id": str(user.user_id),
                        "channel": "email",
                        "subject": "Bienvenida",
                        "body": "Bienvenido a nuestra plataforma!",
                        "recipient": "notif@ttm.com",
                    }
                },
            }
        ]))
        assert result.error is None
        op = result.content[0]
        assert op["success"] is True
        notif = _to_dict(op["result"])
        assert notif["subject"] == "Bienvenida"
        assert notif["channel"] == "email"


class TestChatFinancialReportViaTools:

    def test_financial_report(self, manager, user_factory, order_factory, payment_factory):
        """Simula: 'Hazme un reporte de finanzas completo'.

        El agente necesita:
        1. Listar todos los pedidos
        2. Listar todos los pagos
        3. Calcular totales
        """
        user_a = user_factory(user_name="Alice", email="alice@report.com")
        user_b = user_factory(user_name="Bob", email="bob@report.com")

        order_factory(user=user_a, product_name="Widget A", quantity=3, unit_price=50.00)
        order_factory(user=user_b, product_name="Widget B", quantity=1, unit_price=200.00)
        order_factory(user=user_a, product_name="Widget C", quantity=2, unit_price=75.00)

        commerce_spec = _find_spec(manager, "commerce")
        result = _run(commerce_spec.call(operations=[
            {"method": "list_orders", "args": {}},
            {"method": "list_payments", "args": {}},
        ]))

        assert result.error is None
        assert len(result.content) == 2

        orders = [_to_dict(o) for o in result.content[0]["result"]]
        payments = [_to_dict(p) for p in result.content[1]["result"]]

        assert len(orders) == 3
        assert len(payments) == 0

        total_orders = sum(o["quantity"] * o["unit_price"] for o in orders)
        assert total_orders == 500.00

    def test_financial_report_with_payments(self, manager, user_factory, order_factory, payment_factory):
        """Reporte financiero con pagos registrados."""
        user = user_factory(user_name="Buyer", email="buyer@report.com")

        order1 = order_factory(user=user, product_name="Item 1", quantity=2, unit_price=100.00)
        order_factory(user=user, product_name="Item 2", quantity=1, unit_price=500.00)

        payment_factory(order=order1, amount=200.00, method="credit_card")

        commerce_spec = _find_spec(manager, "commerce")
        result = _run(commerce_spec.call(operations=[
            {"method": "list_orders", "args": {"user_id": str(user.user_id)}},
            {"method": "list_payments", "args": {"order_id": str(order1.order_id)}},
        ]))

        assert result.error is None
        orders = [_to_dict(o) for o in result.content[0]["result"]]
        payments = [_to_dict(p) for p in result.content[1]["result"]]
        assert len(orders) == 2
        assert len(payments) == 1
        assert payments[0]["amount"] == 200.00

    def test_inventory_report(self, manager, product_factory):
        """Reporte de inventario: listar productos y verificar stock bajo."""
        product_factory(name="High Stock", sku="HS-001", stock=100, price=10.00)
        product_factory(name="Low Stock", sku="LS-001", stock=3, price=50.00)
        product_factory(name="Out of Stock", sku="OS-001", stock=0, price=25.00)

        commerce_spec = _find_spec(manager, "commerce")
        result = _run(commerce_spec.call(operations=[
            {"method": "list_products", "args": {}},
            {"method": "get_low_stock", "args": {"threshold": 10}},
        ]))

        assert result.error is None
        all_products = [_to_dict(p) for p in result.content[0]["result"]]
        low_stock = [_to_dict(p) for p in result.content[1]["result"]]

        assert len(all_products) == 3
        assert len(low_stock) == 2
        low_skus = [p["sku"] for p in low_stock]
        assert "LS-001" in low_skus
        assert "OS-001" in low_skus
        assert "HS-001" not in low_skus


class TestChatMultiServiceBatchViaTools:

    def test_create_user_order_and_payment_in_one_call(self, manager):
        """Batch completo: crear usuario, pedido y pago en una sola llamada al tool.

        Simula lo que haria un agente AI en una sola llamada tool.
        """
        user_spec = _find_spec(manager, "user_service")
        user_res = _run(user_spec.call(operations=[
            {
                "method": "create_user",
                "args": {"data": {"user_name": "Multi", "email": "multi@ttm.com", "password": "pass"}},
            }
        ]))
        user = _to_dict(user_res.content[0]["result"])

        commerce_spec = _find_spec(manager, "commerce")
        result = _run(commerce_spec.call(operations=[
            {
                "method": "create_order",
                "args": {
                    "data": {
                        "user_id": user["user_id"],
                        "product_name": "Combo Package",
                        "quantity": 1,
                        "unit_price": 500.00,
                    }
                },
            },
        ]))

        order = _to_dict(result.content[0]["result"])

        pay_result = _run(commerce_spec.call(operations=[
            {
                "method": "create_payment",
                "args": {
                    "data": {
                        "order_id": order["order_id"],
                        "amount": 500.00,
                        "method": "bank_transfer",
                    }
                },
            },
        ]))

        assert pay_result.content[0]["success"] is True
        assert _to_dict(pay_result.content[0]["result"])["status"] == "completed"


class TestChatErrorHandlingViaTools:

    def test_create_duplicate_user_email(self, manager):
        """Simula error: crear usuario con email duplicado."""
        user_spec = _find_spec(manager, "user_service")
        _run(user_spec.call(operations=[
            {
                "method": "create_user",
                "args": {"data": {"user_name": "First", "email": "dup@ttm.com", "password": "pass"}},
            }
        ]))
        result = _run(user_spec.call(operations=[
            {
                "method": "create_user",
                "args": {"data": {"user_name": "Second", "email": "dup@ttm.com", "password": "pass"}},
            }
        ]))
        assert result.content[0]["success"] is False
        assert "already exists" in result.content[0]["error"]["message"].lower()

    def test_get_nonexistent_user(self, manager):
        """Simula error: buscar usuario que no existe."""
        user_spec = _find_spec(manager, "user_service")
        fake_id = str(uuid4())
        result = _run(user_spec.call(operations=[
            {"method": "get_user", "args": {"data": {"user_id": fake_id}}}
        ]))
        assert result.content[0]["success"] is False
        assert "not found" in result.content[0]["error"]["message"].lower()

    def test_invalid_operation_name(self, manager):
        """Simula error: llamar un metodo que no existe."""
        user_spec = _find_spec(manager, "user_service")
        result = _run(user_spec.call(operations=[
            {"method": "hack_database", "args": {}}
        ]))
        assert result.content[0]["success"] is False
        assert "unknown" in result.content[0]["error"]["message"].lower()

    def test_empty_operations_list(self, manager):
        """Simula error: lista de operaciones vacia."""
        user_spec = _find_spec(manager, "user_service")
        result = _run(user_spec.call(operations=[]))
        assert result.error is not None

    def test_partial_batch_failure(self, manager):
        """Batch parcial: una operacion falla pero la otra tiene exito."""
        user_spec = _find_spec(manager, "user_service")
        _run(user_spec.call(operations=[
            {
                "method": "create_user",
                "args": {"data": {"user_name": "Existing", "email": "existing@ttm.com", "password": "pass"}},
            }
        ]))
        result = _run(user_spec.call(operations=[
            {
                "method": "create_user",
                "args": {"data": {"user_name": "Existing", "email": "existing@ttm.com", "password": "pass"}},
            },
            {
                "method": "create_user",
                "args": {"data": {"user_name": "New User", "email": "new@ttm.com", "password": "pass"}},
            },
        ]))
        assert result.content[0]["success"] is False
        assert result.content[1]["success"] is True
