from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import init_db, seed_admin
from app.exception import AppException
from app.router.api import api_routers
from app.router.web import web_routers


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_admin()
    yield


app = FastAPI(
    title="ToToolManager Example App",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    redirect_slashes=True,
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    is_htmx = request.headers.get("HX-Request") == "true"
    content = {"success": False, "error": exc.message, "detail": exc.detail}
    if is_htmx:
        return JSONResponse(
            status_code=400,
            content=content,
            headers={"HX-Trigger": "showToast"},
        )
    return JSONResponse(status_code=400, content=content)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "frontend" / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

for router in web_routers:
    app.include_router(router)

for router in api_routers:
    app.include_router(router)
