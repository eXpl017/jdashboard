from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Text, and_, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models import Job, ScrapeRun, ScrapeSourceResult, utcnow

# Fields refreshed from the source on every successful sighting.
MUTABLE_JOB_FIELDS = (
    "source_job_id",
    "url",
    "title",
    "company",
    "location",
    "remote_type",
    "employment_type",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_text",
    "description_text",
    "description_html",
    "posted_at",
    "posted_at_raw",
    "source_updated_at",
    "expires_at",
    "security_score",
    "security_tags",
    "role_category",
    "language",
    "location_scope",
    "overseas_eligible",
    "japanese_level",
    "visa_sponsorship",
    "date_confidence",
    "raw_json",
)


def _apply_job_defaults(job: Job) -> None:
    """Fill Python-side defaults so an update never writes NULL to NOT NULL columns."""
    if job.salary_currency is None:
        job.salary_currency = "JPY"
    if job.is_active is None:
        job.is_active = True
    if job.security_score is None:
        job.security_score = 0.0
    if job.security_tags is None:
        job.security_tags = []
    if job.role_category is None:
        job.role_category = "other"
    if job.language is None:
        job.language = "unknown"
    if job.location_scope is None:
        job.location_scope = "unknown"
    if job.date_confidence is None:
        job.date_confidence = "low"


def upsert_job(session: Session, job: Job) -> tuple[Job, bool]:
    """Insert a job or refresh an existing row by fingerprint.

    Returns the persisted job and ``True`` when it was newly created.
    """
    _apply_job_defaults(job)

    existing = session.execute(
        select(Job).where(Job.fingerprint == job.fingerprint)
    ).scalar_one_or_none()

    if existing is not None:
        for field in MUTABLE_JOB_FIELDS:
            setattr(existing, field, getattr(job, field))
        existing.last_seen_at = utcnow()
        existing.is_active = bool(job.is_active)
        session.flush()
        return existing, False

    job.first_seen_at = utcnow()
    job.last_seen_at = job.first_seen_at
    session.add(job)
    session.flush()
    return job, True


def upsert_many(session: Session, jobs: list[Job]) -> tuple[int, int]:
    """Upsert a batch and return ``(created, updated)`` counts."""
    created = 0
    updated = 0
    for job in jobs:
        _, was_created = upsert_job(session, job)
        if was_created:
            created += 1
        else:
            updated += 1
    return created, updated


def get_job(session: Session, job_id: int) -> Job | None:
    return session.get(Job, job_id)


def _job_conditions(
    *,
    q: str | None = None,
    source: str | None = None,
    role: str | None = "technical",
    language: str | None = None,
    location: str | None = None,
    location_scope: str | None = "japan",
    remote: str | None = None,
    visa: str | None = None,
    tag: str | None = None,
    days: int = 3,
    include_active: bool = False,
) -> list[Any]:
    """Build the shared SQLAlchemy filters for jobs and stats."""
    conditions: list[Any] = [Job.is_active.is_(True)]

    days = max(days, 0)
    cutoff = datetime.now(UTC) - timedelta(days=days) if days > 0 else None
    if not include_active and cutoff is not None:
        conditions.append(Job.posted_at.is_not(None))
        conditions.append(Job.posted_at >= cutoff)

    if source:
        conditions.append(Job.source == source)
    if q:
        pattern = f"%{q}%"
        conditions.append(
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.description_text.ilike(pattern),
            )
        )
    if remote:
        conditions.append(Job.remote_type == remote)
    if role and role != "all":
        if role == "technical":
            conditions.append(Job.role_category.in_(("engineering", "operations")))
        else:
            conditions.append(Job.role_category == role)
    if language and language not in ("any", "all"):
        if language == "en":
            conditions.append(Job.language.in_(("en", "bilingual")))
        elif language == "ja":
            conditions.append(Job.language.in_(("ja", "bilingual")))
        else:
            conditions.append(Job.language == language)
    if location_scope and location_scope != "all":
        if location_scope == "japan":
            conditions.append(
                Job.location_scope.in_(("japan_onsite", "japan_hybrid", "japan_remote"))
            )
        else:
            conditions.append(Job.location_scope == location_scope)
    if location:
        conditions.append(Job.location.ilike(f"%{location}%"))
    if visa and visa != "any":
        if visa == "overseas":
            conditions.append(Job.overseas_eligible == 1)
        elif visa == "sponsored":
            conditions.append(Job.visa_sponsorship.is_not(None))
        elif visa == "either":
            conditions.append(
                or_(Job.overseas_eligible == 1, Job.visa_sponsorship.is_not(None))
            )
    if tag:
        # JSON is stored as text on SQLite; cast avoids JSON-specific operators.
        conditions.append(cast(Job.security_tags, Text).like(f'%"{tag}"%'))

    return conditions


def query_jobs(
    session: Session,
    *,
    q: str | None = None,
    source: str | None = None,
    role: str | None = "technical",
    language: str | None = None,
    location: str | None = None,
    location_scope: str | None = "japan",
    remote: str | None = None,
    visa: str | None = None,
    tag: str | None = None,
    days: int = 3,
    include_active: bool = False,
    sort: str = "posted_desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Job], int]:
    """Return ``(jobs, total)`` for the dashboard filters."""
    conditions = _job_conditions(
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
    )

    stmt = select(Job).where(and_(*conditions))
    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    order_by = {
        "posted_desc": (Job.posted_at.desc(), Job.id.desc()),
        "posted_asc": (Job.posted_at.asc(), Job.id.asc()),
        "company": (Job.company.asc(), Job.posted_at.desc()),
        "relevance": (Job.security_score.desc(), Job.posted_at.desc()),
    }.get(sort, (Job.posted_at.desc(), Job.id.desc()))

    stmt = stmt.order_by(*order_by).limit(limit).offset(offset)
    jobs = list(session.execute(stmt).scalars().all())
    return jobs, total


def get_stats(
    session: Session,
    *,
    window_days: int = 3,
    q: str | None = None,
    source: str | None = None,
    role: str | None = "technical",
    language: str | None = None,
    location: str | None = None,
    location_scope: str | None = "japan",
    remote: str | None = None,
    visa: str | None = None,
    tag: str | None = None,
    include_active: bool = False,
) -> dict[str, Any]:
    """Return summary counts for the current filter set.

    ``total_jobs``, ``new_in_window`` and ``relocation_friendly`` respect the
    active filters. The ``by_*`` breakdowns are intentionally global so they
    can populate filter controls without collapsing to the current selection.
    """
    conditions = _job_conditions(
        q=q,
        source=source,
        role=role,
        language=language,
        location=location,
        location_scope=location_scope,
        remote=remote,
        visa=visa,
        tag=tag,
        days=window_days,
        include_active=include_active,
    )

    total_jobs = session.execute(
        select(func.count()).select_from(Job).where(and_(*conditions))
    ).scalar_one()

    if window_days > 0:
        cutoff = datetime.now(UTC) - timedelta(days=window_days)
        new_conditions = [
            *conditions,
            Job.posted_at.is_not(None),
            Job.posted_at >= cutoff,
        ]
        new_in_window = session.execute(
            select(func.count()).select_from(Job).where(and_(*new_conditions))
        ).scalar_one()
    else:
        new_in_window = 0

    relocation_friendly = session.execute(
        select(func.count())
        .select_from(Job)
        .where(
            and_(*conditions),
            or_(Job.overseas_eligible == 1, Job.visa_sponsorship.is_not(None)),
        )
    ).scalar_one()

    by_source_rows = session.execute(
        select(Job.source, func.count())
        .where(Job.is_active.is_(True))
        .group_by(Job.source)
        .order_by(Job.source)
    ).all()
    by_source = {source_name: count for source_name, count in by_source_rows}

    by_role_rows = session.execute(
        select(Job.role_category, func.count())
        .where(Job.is_active.is_(True))
        .group_by(Job.role_category)
        .order_by(Job.role_category)
    ).all()
    by_role_category = {category: count for category, count in by_role_rows}

    tag_rows = session.execute(
        select(Job.security_tags).where(Job.is_active.is_(True))
    ).scalars()
    tag_counter: Counter[str] = Counter()
    for tags in tag_rows:
        if isinstance(tags, list):
            tag_counter.update(str(item) for item in tags if item)
    by_tag = dict(sorted(tag_counter.items()))

    last_run = session.execute(
        select(ScrapeRun).order_by(ScrapeRun.id.desc()).limit(1)
    ).scalar_one_or_none()

    return {
        "total_jobs": total_jobs,
        "new_in_window": new_in_window,
        "by_source": by_source,
        "by_role_category": by_role_category,
        "by_tag": by_tag,
        "relocation_friendly": relocation_friendly,
        "last_run": last_run,
    }


def get_source_health(session: Session) -> dict[str, dict[str, Any]]:
    """Return the latest result and last success for each source.

    The local database is small, so scanning source results newest-first is
    simpler than a window-function query and keeps SQLite compatibility.
    """
    rows = session.execute(
        select(ScrapeSourceResult).order_by(ScrapeSourceResult.id.desc())
    ).scalars()
    latest: dict[str, ScrapeSourceResult] = {}
    last_success: dict[str, datetime] = {}
    for row in rows:
        latest.setdefault(row.source, row)
        if row.status == "success" and row.source not in last_success:
            last_success[row.source] = row.finished_at or row.started_at
    return {
        source: {
            "last_status": latest.get(source).status if source in latest else "never",
            "last_success_at": last_success.get(source),
            "last_error": latest.get(source).error_message if source in latest else None,
        }
        for source in set(latest) | set(last_success)
    }


def create_run(
    session: Session, *, trigger: str = "manual", window_days: int = 3
) -> ScrapeRun:
    run = ScrapeRun(
        started_at=utcnow(),
        status="running",
        trigger=trigger,
        window_days=window_days,
    )
    session.add(run)
    session.flush()
    return run


def finish_run(
    session: Session,
    run_id: int,
    *,
    status: str,
    total_found: int = 0,
    total_new: int = 0,
    total_updated: int = 0,
    total_errors: int = 0,
    error_summary: str | None = None,
) -> ScrapeRun:
    run = session.get(ScrapeRun, run_id)
    if run is None:
        raise ValueError(f"Scrape run {run_id} not found")
    run.status = status
    run.finished_at = utcnow()
    run.total_found = total_found
    run.total_new = total_new
    run.total_updated = total_updated
    run.total_errors = total_errors
    run.error_summary = error_summary
    session.flush()
    return run


def create_source_result(
    session: Session,
    *,
    run_id: int,
    source: str,
    status: str = "running",
    started_at: datetime | None = None,
) -> ScrapeSourceResult:
    result = ScrapeSourceResult(
        run_id=run_id,
        source=source,
        status=status,
        started_at=started_at or utcnow(),
    )
    session.add(result)
    session.flush()
    return result


def finish_source_result(
    session: Session,
    result_id: int,
    *,
    status: str,
    found: int = 0,
    new: int = 0,
    updated: int = 0,
    skipped: int = 0,
    errors: int = 0,
    error_message: str | None = None,
) -> ScrapeSourceResult:
    result = session.get(ScrapeSourceResult, result_id)
    if result is None:
        raise ValueError(f"Scrape source result {result_id} not found")
    result.status = status
    result.finished_at = utcnow()
    result.found = found
    result.new = new
    result.updated = updated
    result.skipped = skipped
    result.errors = errors
    result.error_message = error_message
    session.flush()
    return result
