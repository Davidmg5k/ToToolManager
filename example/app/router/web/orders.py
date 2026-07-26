from fastapi import APIRouter, Request, Depends

from app.auth import require_admin
from app.templates import templates

orders_router = APIRouter(tags=["web"])


@orders_router.get("/admin/orders")
async def orders(request: Request, user=Depends(require_admin)):
    return templates.TemplateResponse(request, "page/admin/orders.html")
