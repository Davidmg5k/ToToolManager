from fastapi import APIRouter, Request, Depends

from app.auth import require_admin
from app.templates import templates

dashboard_router = APIRouter(tags=["web"])


@dashboard_router.get("/admin/dashboard")
async def dashboard(request: Request, user=Depends(require_admin)):
    return templates.TemplateResponse(request, "page/admin/dashboard.html")
