from pathlib import Path

from fastapi.templating import Jinja2Templates


# Resolve from this module so Uvicorn can be launched from any working directory.
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
