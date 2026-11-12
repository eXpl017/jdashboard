from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import models
from app.api import api_router
from app.config import settings
from app.db import engine
from app.logging_config import configure_logging

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Prepare the SQLite file and schema. No scraping happens here."""
    configure_logging()
    if settings.database_url.startswith("sqlite:///"):
        db_path = settings.database_url.removeprefix("sqlite:///")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    models.Base.metadata.create_all(bind=engine)
    try:
        yield
    finally:
        service = getattr(_app.state, "refresh_service", None)
        if service is not None:
            await service.aclose()


app = FastAPI(
    title="Japan Cybersecurity Jobs",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(api_router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request) -> HTMLResponse:
    """Serve the minimal dashboard UI."""
    return templates.TemplateResponse(request, "index.html", {"app_name": settings.app_name})
