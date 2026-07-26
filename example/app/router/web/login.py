from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.templates import templates

login_router = APIRouter(tags=["web"])


@login_router.get("/login")
async def login_page(request: Request):
    from app.auth import get_current_user
    user = get_current_user(request)
    if user is not None:
        return RedirectResponse("/admin/dashboard", status_code=302)
    return templates.TemplateResponse(request, "page/login.html")
