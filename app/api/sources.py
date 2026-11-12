from fastapi import APIRouter, Depends

from app import repository, schemas
from app.config import settings
from app.db import get_session
from app.scrapers.registry import SCRAPER_CLASSES

router = APIRouter()


@router.get("/api/sources", response_model=schemas.SourceListResponse, tags=["sources"])
def list_sources(session=Depends(get_session)) -> schemas.SourceListResponse:
    """Return the registered sources with their latest refresh status."""
    health = repository.get_source_health(session)
    sources = []
    for source_id, scraper_cls in SCRAPER_CLASSES.items():
        state = health.get(source_id, {})
        sources.append(
            schemas.SourceRead(
                id=source_id,
                name=scraper_cls.source_name,
                url=scraper_cls.listing_url,
                enabled=bool(getattr(settings, f"enable_{source_id}", True)),
                last_status=state.get("last_status", "never"),
                last_success_at=state.get("last_success_at"),
                last_error=state.get("last_error"),
            )
        )
    return schemas.SourceListResponse(sources=sources)
