from pathlib import Path

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

_TEMPLATE_DIR = Path(__file__).parent.parent / "frontend" / "src"

templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


def _is_admin(request: Request) -> bool:
    return request.url.path.startswith("/admin/")


templates.env.globals["admin"] = _is_admin
