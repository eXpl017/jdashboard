"""Run a single-source scrape and print the parsed jobs.

Does not write to the database; intended for parser development and smoke tests.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.logging_config import configure_logging
from app.scrapers.base import BaseScraper, ScrapeResult
from app.scrapers.registry import build_registry
from app.services.http import HttpClient


def _job_payload(scraper: BaseScraper, job) -> dict[str, object]:
    return {
        "source": job.source,
        "source_job_id": job.source_job_id,
        "url": job.url,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "remote_type": job.remote_type,
        "employment_type": job.employment_type,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency,
        "salary_text": job.salary_text,
        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
        "japanese_level": job.japanese_level,
        "visa_sponsorship": job.visa_sponsorship,
        "overseas_eligible": job.overseas_eligible,
        "role_category": job.role_category,
        "language": job.language,
        "location_scope": job.location_scope,
        "security_score": job.security_score,
        "security_tags": job.security_tags,
        "source_is_security_category": scraper.is_security_category,
    }


def _since(days: int) -> datetime:
    """Return the timezone-aware UTC cutoff the scrapers expect."""
    return datetime.now(UTC) - timedelta(days=days)


async def run_source(source_id: str, days: int) -> dict[str, object]:
    registry = build_registry(HttpClient(settings), settings)
    scraper = registry.get(source_id)
    if scraper is None:
        raise SystemExit(f"Unknown source: {source_id}")

    result: ScrapeResult = await scraper.scrape(_since(days))
    jobs = [_job_payload(scraper, job) for job in result.jobs]
    return {
        "source": source_id,
        "status": "ok" if not result.errors else "partial",
        "found": result.found,
        "skipped": result.skipped,
        "errors": result.errors,
        "jobs": jobs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect a single source scrape.")
    parser.add_argument("source", help="Source ID, e.g. michael_page")
    parser.add_argument("--days", type=int, default=settings.default_window_days)
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of jobs to print")
    args = parser.parse_args(argv)

    if args.days < 1 or args.days > 30:
        parser.error("--days must be between 1 and 30")

    configure_logging()

    result = asyncio.run(run_source(args.source, args.days))
    jobs = list(result.get("jobs") or [])
    if args.limit > 0:
        jobs = jobs[: args.limit]
    payload = dict(result)
    payload["jobs"] = jobs
    print(json.dumps(payload, default=str, ensure_ascii=False, indent=2))
    return 0 if not (result.get("errors") or []) else 1


if __name__ == "__main__":
    raise SystemExit(main())
