from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import repository, schemas
from app.db import get_session
from app.models import Job
from app.scrapers.registry import SOURCE_NAMES

router = APIRouter()


def _to_job_read(job: Job, *, window_days: int) -> schemas.JobRead:
    item = schemas.JobRead.model_validate(job)
    item.source_name = SOURCE_NAMES.get(job.source, job.source)
    if window_days > 0:
        first_seen = job.first_seen_at
        if first_seen.tzinfo is None:
            first_seen = first_seen.replace(tzinfo=UTC)
        cutoff = datetime.now(UTC) - timedelta(days=window_days)
        item.is_new = first_seen >= cutoff
    return item


@router.get("/api/jobs", response_model=schemas.JobListResponse, tags=["jobs"])
def list_jobs(
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
    sort: str = Query(default="posted_desc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> schemas.JobListResponse:
    jobs, total = repository.query_jobs(
        session,
        q=q,
        source=source,
        role=role,
        language=language,
        location=location,
        location_scope=location_scope,
        remote=remote,
        visa=visa,
        tag=tag,
        days=days,
        include_active=include_active,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    items = [_to_job_read(job, window_days=days) for job in jobs]
    return schemas.JobListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/api/jobs/{job_id}", response_model=schemas.JobRead, tags=["jobs"])
def get_job(job_id: int, session: Session = Depends(get_session)) -> schemas.JobRead:
    job = repository.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_job_read(job, window_days=3)
