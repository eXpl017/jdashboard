from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app import models
from app.api import api_router
from app.config import settings
from app.db import engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Prepare the SQLite file and schema. No scraping happens here."""
    if settings.database_url.startswith("sqlite:///"):
        db_path = settings.database_url.removeprefix("sqlite:///")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    models.Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Japan Cybersecurity Jobs",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)
