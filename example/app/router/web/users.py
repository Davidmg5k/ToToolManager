from fastapi import APIRouter, Request, Depends

from app.auth import require_admin
from app.templates import templates

users_router = APIRouter(tags=["web"])


@users_router.get("/admin/users")
async def users(request: Request, user=Depends(require_admin)):
    return templates.TemplateResponse(request, "page/admin/users.html")
