from fastapi import APIRouter, Request

from app.templates import templates

web_router = APIRouter(tags=["web"])


@web_router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "page/index.html")
