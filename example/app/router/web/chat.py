from fastapi import APIRouter, Request, Depends

from app.auth import require_admin
from app.templates import templates

chat_router = APIRouter(tags=["web"])


@chat_router.get("/admin/chat")
async def chat(request: Request, user=Depends(require_admin)):
    return templates.TemplateResponse(request, "page/admin/chat.html")
