import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.refresh import refresh_status, start_refresh
from app.main import app
from app.models import Job, ScrapeRun, ScrapeSourceResult
from app.scrapers.base import (
    BaseScraper,
    RobotsDisallowed,
    ScrapedJob,
    ScraperError,
    ScrapeResult,
)
from app.services.refresh import RefreshAlreadyRunning, RefreshService


class FakeScraper(BaseScraper):
    source_id = "fake"
    source_name = "Fake"
    listing_url = "https://example.com/jobs"
    is_security_category = True

    def __init__(self, *, jobs: list[ScrapedJob] | None = None, error=None) -> None:
        self.jobs = jobs or []
        self.error = error

    async def scrape(self, since: datetime) -> ScrapeResult:
        if self.error is not None:
            raise self.error
        return ScrapeResult(
            source=self.source_id, jobs=self.jobs, found=len(self.jobs)
        )


class BlockingScraper(FakeScraper):
    def __init__(self, gate: asyncio.Event) -> None:
        super().__init__()
        self.gate = gate

    async def scrape(self, since: datetime) -> ScrapeResult:
        await self.gate.wait()
        return ScrapeResult(source=self.source_id, jobs=[], found=0)


def _scraped(**overrides) -> ScrapedJob:
    defaults = {
        "source": "fake",
        "url": "https://example.com/jobs/1",
        "title": "Security Engineer",
        "company": "Acme",
        "location": "Tokyo",
        "remote_type": "hybrid",
        "description_text": "AppSec and cloud security",
        "posted_at": datetime.now(UTC) - timedelta(days=1),
    }
    defaults.update(overrides)
    return ScrapedJob(**defaults)


@pytest.mark.asyncio
async def test_refresh_success_persists_jobs_and_run(session_factory):
    service = RefreshService(
        session_factory=session_factory,
        scrapers={"fake": FakeScraper(jobs=[_scraped()])},
    )

    progress = await service.start()
    assert progress.status == "running"
    assert progress.sources["fake"].status == "pending"

    await service.wait()

    snapshot = service.snapshot()
    assert snapshot is not None
    assert snapshot.status == "success"
    assert snapshot.sources["fake"].status == "success"
    assert snapshot.sources["fake"].new == 1
    assert snapshot.current_source is None

    db = session_factory()
    try:
        jobs = db.execute(select(Job)).scalars().all()
        assert len(jobs) == 1
        job = jobs[0]
        assert job.title == "Security Engineer"
        assert job.role_category == "engineering"
        assert job.language == "en"
        assert job.location_scope == "japan_hybrid"
        assert job.security_score > 0
        assert "security-engineering" in job.security_tags

        run = db.execute(select(ScrapeRun)).scalar_one()
        assert run.status == "success"
        assert run.total_new == 1

        source_result = db.execute(select(ScrapeSourceResult)).scalar_one()
        assert source_result.status == "success"
        assert source_result.new == 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_refresh_partial_failure_keeps_good_jobs(session_factory):
    service = RefreshService(
        session_factory=session_factory,
        scrapers={
            "good": FakeScraper(jobs=[_scraped(source="good")]),
            "bad": FakeScraper(error=ScraperError("listing selector changed")),
            "blocked": FakeScraper(
                error=RobotsDisallowed("robots.txt disallows /jobs")
            ),
        },
    )

    await service.start()
    await service.wait()

    snapshot = service.snapshot()
    assert snapshot is not None
    assert snapshot.status == "partial"
    assert snapshot.sources["good"].status == "success"
    assert snapshot.sources["bad"].status == "error"
    assert snapshot.sources["bad"].error_message == "listing selector changed"
    assert snapshot.sources["blocked"].status == "skipped"

    db = session_factory()
    try:
        assert len(db.execute(select(Job)).scalars().all()) == 1
        run = db.execute(select(ScrapeRun)).scalar_one()
        assert run.status == "partial"
        results = {
            row.source: row
            for row in db.execute(select(ScrapeSourceResult)).scalars().all()
        }
        assert results["good"].status == "success"
        assert results["bad"].status == "error"
        assert results["blocked"].status == "skipped"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_refresh_marks_expired_jobs_inactive(session_factory):
    expired_job = _scraped(
        source="fake",
        url="https://example.com/jobs/expired",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    service = RefreshService(
        session_factory=session_factory,
        scrapers={"fake": FakeScraper(jobs=[expired_job])},
    )
    await service.start()
    await service.wait()
    assert service.snapshot() is not None
    assert service.snapshot().status == "success"

    db = session_factory()
    try:
        job = db.execute(select(Job)).scalar_one()
        assert job.is_active is False
    finally:
        db.close()


@pytest.mark.asyncio
async def test_second_start_raises_while_running(session_factory):
    gate = asyncio.Event()
    service = RefreshService(
        session_factory=session_factory,
        scrapers={"fake": BlockingScraper(gate)},
    )

    await service.start()
    with pytest.raises(RefreshAlreadyRunning):
        await service.start()

    gate.set()
    await service.wait()
    assert service.snapshot().status == "success"


@pytest.mark.asyncio
async def test_start_refresh_endpoint_starts_run(session_factory):
    service = RefreshService(
        session_factory=session_factory,
        scrapers={"fake": FakeScraper(jobs=[_scraped()])},
    )

    response = await start_refresh(payload=None, service=service)
    assert response.status == "running"
    assert response.run_id == service.snapshot().run_id

    await service.wait()
    assert service.snapshot().status == "success"


@pytest.mark.asyncio
async def test_start_refresh_endpoint_returns_409(session_factory):
    gate = asyncio.Event()
    service = RefreshService(
        session_factory=session_factory,
        scrapers={"fake": BlockingScraper(gate)},
    )

    await service.start()
    with pytest.raises(HTTPException) as exc_info:
        await start_refresh(payload=None, service=service)
    assert exc_info.value.status_code == 409

    gate.set()
    await service.wait()


@pytest.mark.asyncio
async def test_refresh_status_reports_progress(session_factory):
    service = RefreshService(
        session_factory=session_factory,
        scrapers={"fake": FakeScraper(jobs=[_scraped()])},
    )
    await service.start()
    await service.wait()

    status = await refresh_status(service=service)
    assert status.run_id == service.snapshot().run_id
    assert status.status == "success"
    assert status.started_at is not None
    assert status.finished_at is not None
    assert status.sources["fake"].status == "success"


def test_refresh_status_idle(client, session_factory):
    service = RefreshService(session_factory=session_factory, scrapers={})
    app.state.refresh_service = service
    try:
        response = client.get("/api/refresh/status")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "idle"
        assert body["run_id"] is None
        assert body["sources"] == {}
    finally:
        del app.state.refresh_service
