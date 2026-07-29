from fastapi import APIRouter
from sqlmodel import Session, select

from app import engine
from app.model import User, Order, Product, PaymentRecord
from app.response import ok

dashboard_router = APIRouter(prefix="/api/dashboard", tags=["api", "dashboard"])


@dashboard_router.get("/stats")
async def get_stats():
    with Session(engine) as session:
        users_count = len(session.exec(select(User)).all())
        orders_count = len(session.exec(select(Order)).all())
        products_count = len(session.exec(select(Product)).all())
        payments_count = len(session.exec(select(PaymentRecord)).all())

        recent_orders = [
            {
                "order_id": str(o.order_id),
                "product_name": o.product_name,
                "status": o.status,
                "quantity": o.quantity,
                "unit_price": o.unit_price,
            }
            for o in session.exec(select(Order).order_by(Order.order_id.desc()).limit(5)).all()
        ]

        low_stock = [
            {
                "product_id": str(p.product_id),
                "name": p.name,
                "sku": p.sku,
                "stock": p.stock,
            }
            for p in session.exec(select(Product).where(Product.stock <= 10).order_by(Product.stock.asc()).limit(5)).all()
        ]

    return ok({
        "users": users_count,
        "orders": orders_count,
        "products": products_count,
        "payments": payments_count,
        "recent_orders": recent_orders,
        "low_stock_products": low_stock,
    })

