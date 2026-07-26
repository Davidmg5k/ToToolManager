from pathlib import Path

from fastapi.templating import Jinja2Templates

_TEMPLATE_DIR = Path(__file__).parent.parent / "frontend" / "src"

templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
