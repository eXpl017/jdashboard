import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import repository
from app.config import Settings
from app.config import settings as default_settings
from app.db import SessionLocal
from app.models import Job, utcnow
from app.scrapers.base import (
    BaseScraper,
    RobotsDisallowed,
    ScrapedJob,
)
from app.scrapers.registry import build_registry
from app.services.classify import classify
from app.services.dates import to_utc
from app.services.http import HttpClient
from app.services.normalize import (
    detect_employment_type,
    detect_location_scope,
    detect_overseas_eligible,
    detect_remote,
    fingerprint,
    strip_html,
)

logger = logging.getLogger(__name__)


class RefreshAlreadyRunning(Exception):
    """Raised when a second refresh starts before the first one finishes."""


@dataclass(slots=True)
class SourceProgress:
    source: str
    status: str = "pending"  # pending | running | success | error | skipped
    found: int = 0
    new: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    error_message: str | None = None


@dataclass(slots=True)
class RefreshProgress:
    run_id: int
    started_at: datetime
    status: str = "running"  # running | success | partial | failed
    finished_at: datetime | None = None
    current_source: str | None = None
    sources: dict[str, SourceProgress] = field(default_factory=dict)


class RefreshService:
    """Run enabled scrapers sequentially on explicit request.

    Progress lives in memory for the UI; ``scrape_runs`` and
    ``scrape_source_results`` are the durable record. Scrapers never write to
    the database themselves.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        scrapers: dict[str, BaseScraper],
        default_window_days: int = 3,
        http: HttpClient | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._scrapers = scrapers
        self._default_window_days = default_window_days
        self._http = http
        self._lock = asyncio.Lock()
        self._progress: RefreshProgress | None = None
        self._task: asyncio.Task[None] | None = None

    async def aclose(self) -> None:
        """Release the shared HTTP client on application shutdown."""
        if self._http is not None:
            await self._http.aclose()

    @property
    def is_running(self) -> bool:
        return self._lock.locked()

    def snapshot(self) -> RefreshProgress | None:
        return self._progress

    async def start(
        self, *, window_days: int | None = None, trigger: str = "manual"
    ) -> RefreshProgress:
        """Start a refresh in the background, or raise if one is already running."""
        if self._lock.locked():
            raise RefreshAlreadyRunning("A refresh is already running.")

        await self._lock.acquire()
        window = window_days if window_days is not None else self._default_window_days
        try:
            run_id = self._create_run(trigger=trigger, window_days=window)
            progress = RefreshProgress(
                run_id=run_id,
                started_at=utcnow(),
                sources={
                    source_id: SourceProgress(source=source_id)
                    for source_id in self._scrapers
                },
            )
            self._progress = progress
            self._task = asyncio.create_task(self._run(progress, window))
            return progress
        except Exception:
            self._lock.release()
            raise

    async def wait(self) -> None:
        """Await the background refresh task (used by tests and scripts)."""
        task = self._task
        if task is not None:
            await task

    async def _run(self, progress: RefreshProgress, window_days: int) -> None:
        since = utcnow() - timedelta(days=window_days)
        totals = {"found": 0, "new": 0, "updated": 0, "errors": 0}
        error_messages: list[str] = []

        try:
            for source_id, scraper in self._scrapers.items():
                source_progress = progress.sources[source_id]
                progress.current_source = source_id
                source_progress.status = "running"
                result_id = self._create_source_result(progress.run_id, source_id)

                try:
                    result = await scraper.scrape(since)
                    created, updated = self._persist_jobs(
                        result.jobs,
                        source_id=source_id,
                        source_is_security_category=scraper.is_security_category,
                    )

                    source_progress.status = "success"
                    source_progress.found = result.found
                    source_progress.new = created
                    source_progress.updated = updated
                    source_progress.skipped = result.skipped
                    source_progress.errors = len(result.errors)

                    totals["found"] += result.found
                    totals["new"] += created
                    totals["updated"] += updated
                    totals["errors"] += len(result.errors)
                    error_messages.extend(result.errors)

                    self._finish_source_result(
                        result_id,
                        status="success",
                        found=result.found,
                        new=created,
                        updated=updated,
                        skipped=result.skipped,
                        errors=len(result.errors),
                        error_message="; ".join(result.errors)[:500] or None,
                    )
                except RobotsDisallowed as exc:
                    message = self._safe_error(exc)
                    source_progress.status = "skipped"
                    source_progress.error_message = message
                    totals["errors"] += 1
                    error_messages.append(f"{source_id}: {message}")
                    self._finish_source_result(
                        result_id,
                        status="skipped",
                        error_message=message,
                    )
                    logger.warning("Source %s skipped: %s", source_id, message)
                except Exception as exc:
                    message = self._safe_error(exc)
                    source_progress.status = "error"
                    source_progress.error_message = message
                    totals["errors"] += 1
                    error_messages.append(f"{source_id}: {message}")
                    self._finish_source_result(
                        result_id,
                        status="error",
                        error_message=message,
                    )
                    logger.exception("Source %s failed", source_id)

            progress.status = self._overall_status(progress)
            progress.finished_at = utcnow()
            progress.current_source = None
            self._finish_run(
                progress.run_id,
                status=progress.status,
                totals=totals,
                error_summary="; ".join(error_messages)[:2000] or None,
            )
        except asyncio.CancelledError:
            logger.warning("Refresh run %s was cancelled", progress.run_id)
            progress.status = "failed"
            progress.finished_at = utcnow()
            progress.current_source = None
            try:
                self._finish_run(
                    progress.run_id,
                    status="failed",
                    totals=totals,
                    error_summary="Refresh cancelled",
                )
            except Exception:
                logger.exception("Could not record cancelled run %s", progress.run_id)
            raise
        except Exception:
            logger.exception("Refresh run %s failed unexpectedly", progress.run_id)
            progress.status = "failed"
            progress.finished_at = utcnow()
            progress.current_source = None
            try:
                self._finish_run(
                    progress.run_id,
                    status="failed",
                    totals=totals,
                    error_summary="Unexpected refresh failure",
                )
            except Exception:
                logger.exception("Could not record failed run %s", progress.run_id)
        finally:
            if self._lock.locked():
                self._lock.release()

    @staticmethod
    def _overall_status(progress: RefreshProgress) -> str:
        if not progress.sources:
            return "failed"
        statuses = [source.status for source in progress.sources.values()]
        if all(status == "success" for status in statuses):
            return "success"
        if not any(status == "success" for status in statuses):
            return "failed"
        return "partial"

    @staticmethod
    def _safe_error(exc: BaseException) -> str:
        message = str(exc).strip()
        if not message:
            message = exc.__class__.__name__
        return message[:500]

    def _create_run(self, *, trigger: str, window_days: int) -> int:
        session = self._session_factory()
        try:
            run = repository.create_run(
                session, trigger=trigger, window_days=window_days
            )
            session.commit()
            return run.id
        finally:
            session.close()

    def _finish_run(
        self,
        run_id: int,
        *,
        status: str,
        totals: dict[str, int],
        error_summary: str | None,
    ) -> None:
        session = self._session_factory()
        try:
            repository.finish_run(
                session,
                run_id,
                status=status,
                total_found=totals["found"],
                total_new=totals["new"],
                total_updated=totals["updated"],
                total_errors=totals["errors"],
                error_summary=error_summary,
            )
            session.commit()
        finally:
            session.close()

    def _create_source_result(self, run_id: int, source: str) -> int:
        session = self._session_factory()
        try:
            result = repository.create_source_result(
                session, run_id=run_id, source=source
            )
            session.commit()
            return result.id
        finally:
            session.close()

    def _finish_source_result(
        self,
        result_id: int,
        *,
        status: str,
        found: int = 0,
        new: int = 0,
        updated: int = 0,
        skipped: int = 0,
        errors: int = 0,
        error_message: str | None = None,
    ) -> None:
        session = self._session_factory()
        try:
            repository.finish_source_result(
                session,
                result_id,
                status=status,
                found=found,
                new=new,
                updated=updated,
                skipped=skipped,
                errors=errors,
                error_message=error_message,
            )
            session.commit()
        finally:
            session.close()

    def _persist_jobs(
        self,
        scraped_jobs: list[ScrapedJob],
        *,
        source_id: str,
        source_is_security_category: bool,
    ) -> tuple[int, int]:
        if not scraped_jobs:
            return 0, 0

        session = self._session_factory()
        try:
            jobs = [
                self._to_job(
                    scraped,
                    source_id=source_id,
                    source_is_security_category=source_is_security_category,
                )
                for scraped in scraped_jobs
            ]
            created, updated = repository.upsert_many(session, jobs)
            session.commit()
            return created, updated
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _to_job(
        scraped: ScrapedJob,
        *,
        source_id: str,
        source_is_security_category: bool,
    ) -> Job:
        if scraped.source != source_id:
            logger.warning(
                "Scraper %s returned a job tagged %s; using the registry source ID",
                source_id,
                scraped.source,
            )
        description_text = scraped.description_text
        if not description_text and scraped.description_html:
            description_text = strip_html(scraped.description_html)

        classification = classify(
            scraped.title,
            description_text,
            source_tags=scraped.security_tags,
            source_is_security_category=source_is_security_category,
        )

        remote_type = scraped.remote_type or detect_remote(
            f"{scraped.location or ''} {description_text or ''}"
        )
        employment_type = scraped.employment_type or detect_employment_type(
            description_text
        )
        location_scope = scraped.location_scope or detect_location_scope(
            scraped.location, remote_type, description_text
        )
        overseas_eligible = scraped.overseas_eligible
        if overseas_eligible is None:
            overseas_eligible = detect_overseas_eligible(description_text)

        tags = sorted(set(scraped.security_tags) | set(classification.tags))

        def _as_utc(value: datetime | None) -> datetime | None:
            return to_utc(value) if value is not None else None

        now = utcnow()
        return Job(
            fingerprint=fingerprint(source_id, scraped.url),
            source=source_id,
            source_job_id=scraped.source_job_id,
            url=scraped.url,
            title=scraped.title,
            company=scraped.company,
            location=scraped.location,
            remote_type=remote_type,
            employment_type=employment_type,
            salary_min=scraped.salary_min,
            salary_max=scraped.salary_max,
            salary_currency=scraped.salary_currency,
            salary_text=scraped.salary_text,
            description_text=description_text,
            description_html=scraped.description_html,
            posted_at=_as_utc(scraped.posted_at),
            posted_at_raw=scraped.posted_at_raw,
            source_updated_at=_as_utc(scraped.source_updated_at),
            expires_at=_as_utc(scraped.expires_at),
            is_active=scraped.expires_at is None or scraped.expires_at > now,
            first_seen_at=now,
            last_seen_at=now,
            security_score=classification.score,
            security_tags=tags,
            role_category=scraped.role_category or classification.role_category,
            language=scraped.language or classification.language,
            location_scope=location_scope,
            overseas_eligible=(
                None if overseas_eligible is None else int(overseas_eligible)
            ),
            japanese_level=scraped.japanese_level,
            visa_sponsorship=scraped.visa_sponsorship,
            date_confidence="high" if scraped.posted_at is not None else "low",
            raw_json=(
                json.dumps(scraped.raw, ensure_ascii=False, default=str)
                if scraped.raw
                else None
            ),
        )


def build_default_refresh_service(config: Settings | None = None) -> RefreshService:
    config = config or default_settings
    http = HttpClient(config)
    return RefreshService(
        session_factory=SessionLocal,
        scrapers=build_registry(http, config),
        default_window_days=config.default_window_days,
        http=http,
    )
