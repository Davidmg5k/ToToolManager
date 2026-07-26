from fastapi import APIRouter, Request, Depends

from app.auth import require_admin
from app.templates import templates

payments_router = APIRouter(tags=["web"])


@payments_router.get("/admin/payments")
async def payments(request: Request, user=Depends(require_admin)):
    return templates.TemplateResponse(request, "page/admin/payments.html")
