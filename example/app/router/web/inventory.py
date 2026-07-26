from fastapi import APIRouter, Request, Depends

from app.auth import require_admin
from app.templates import templates

inventory_router = APIRouter(tags=["web"])


@inventory_router.get("/admin/inventory")
async def inventory(request: Request, user=Depends(require_admin)):
    return templates.TemplateResponse(request, "page/admin/inventory.html")
