from fastapi import APIRouter, Request, Depends

from app.auth import require_admin
from app.templates import templates

notifications_router = APIRouter(tags=["web"])


@notifications_router.get("/admin/notifications")
async def notifications(request: Request, user=Depends(require_admin)):
    return templates.TemplateResponse(request, "page/admin/notifications.html")
