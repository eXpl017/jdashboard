from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import repository, schemas
from app.db import get_session

router = APIRouter()


@router.get("/api/stats", response_model=schemas.StatsResponse, tags=["stats"])
def get_stats(
    session: Session = Depends(get_session),
    q: str | None = Query(default=None, description="Search title, company, description"),
    source: str | None = Query(default=None),
    role: str | None = Query(default="technical"),
    language: str | None = Query(default=None),
    location: str | None = Query(default=None),
    location_scope: str | None = Query(default="japan"),
    remote: str | None = Query(default=None),
    visa: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    days: int = Query(default=3, ge=0),
    include_active: bool = Query(default=False),
) -> schemas.StatsResponse:
    """Summary counts for the dashboard filters (including the time window)."""
    stats = repository.get_stats(
        session,
        window_days=days,
        q=q,
        source=source,
        role=role,
        language=language,
        location=location,
        location_scope=location_scope,
        remote=remote,
        visa=visa,
        tag=tag,
        include_active=include_active,
    )
    return schemas.StatsResponse(**stats)
