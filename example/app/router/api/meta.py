from fastapi import APIRouter

from app.response import ok

meta_router = APIRouter(prefix="/api/meta", tags=["api", "meta"])


@meta_router.get("/enums")
async def get_enums():
    return ok({
        "order_status": ["pending", "confirmed", "shipped", "delivered", "cancelled"],
        "payment_method": ["credit_card", "debit_card", "bank_transfer", "cash"],
        "payment_status": ["pending", "completed", "failed", "refunded"],
        "notification_channel": ["email", "sms", "push"],
        "notification_status": ["pending", "sent", "delivered", "failed"],
    })
