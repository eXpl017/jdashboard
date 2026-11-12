from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.config import Settings
from app.scrapers.base import ParseError
from app.scrapers.japan_dev import _REF_ID_RE, JapanDevScraper
from app.services.http import HttpClient

FIXTURES = "tests/fixtures"


def _read_fixture(name: str) -> str:
    with open(f"{FIXTURES}/{name}", encoding="utf-8") as f:
        return f.read()


@pytest.fixture()
def scraper() -> JapanDevScraper:
    return JapanDevScraper(http=None, settings=None)  # type: ignore[arg-type]


def test_japan_dev_extracts_detail_urls(scraper):
    html = _read_fixture("japan_dev_list.html")
    urls = JapanDevScraper._extract_detail_urls(
        html, "https://japan-dev.com/security-jobs-in-japan"
    )

    assert len(urls) == 10
    for url in urls:
        assert url.startswith("https://japan-dev.com/jobs/")
        # Each URL ends with a slug plus a 6+ char id.
        assert _REF_ID_RE.search(url) is not None
    # Non-job links are ignored.
    assert not any(url.endswith("/jobs") for url in urls)


def test_japan_dev_parses_detail(scraper):
    html = _read_fixture("japan_dev_detail.html")
    url = "https://japan-dev.com/jobs/meetsmore/meetsmore-senior-security-engineer-woeebw"
    job = JapanDevScraper._parse_detail(scraper, html, url)

    assert job is not None
    assert job.source == "japan_dev"
    assert job.source_job_id == "woeebw"
    assert job.url == "https://japan-dev.com/jobs/meetsmore/meetsmore-senior-security-engineer-woeebw"
    assert job.title == "Senior Security Engineer"
    assert job.company == "MeetsMore"
    assert job.location == "Tokyo"
    assert job.remote_type == "hybrid"  # HTML "Partial Remote"
    assert job.employment_type == "full_time"
    assert (job.salary_min, job.salary_max, job.salary_currency) == (
        7_000_000,
        11_000_000,
        "JPY",
    )
    assert job.salary_text == "¥7,000,000 - ¥11,000,000 per year"
    assert job.posted_at_raw == "2026-10-09"
    assert job.posted_at == datetime(2026, 10, 8, 15, 0, tzinfo=UTC)
    assert job.expires_at == datetime(2027, 4, 8, 15, 0, tzinfo=UTC)
    assert job.language == "en"
    assert job.location_scope == "japan_hybrid"
    assert job.overseas_eligible is True  # JP + US + GB
    assert job.role_category == "engineering"
    assert "security-engineering" in job.security_tags


def test_japan_dev_overseas_not_eligible(scraper):
    html = _read_fixture("japan_dev_detail_overseas_no.html")
    url = "https://japan-dev.com/jobs/authlete/authlete-security-lead-f25e3s"
    job = JapanDevScraper._parse_detail(scraper, html, url)
    assert job is not None
    assert job.overseas_eligible is False  # JP only
    assert job.remote_type == "remote"  # Fully Remote
    assert job.location_scope == "japan_remote"


def test_japan_dev_detail_missing_jsonld_raises(scraper):
    with pytest.raises(ParseError):
        JapanDevScraper._parse_detail(
            scraper, "<html><body>no json-ld</body></html>", "https://example.com/x"
        )


@pytest.mark.asyncio
@respx.mock
async def test_japan_dev_full_scrape():
    settings = Settings(
        min_request_interval_seconds=0.0,
        max_retries=0,
        retry_backoff_seconds=0.0,
        request_timeout_seconds=5.0,
    )
    http = HttpClient(settings)
    scraper = JapanDevScraper(http=http, settings=settings)

    listing_html = _read_fixture("japan_dev_list.html")
    detail_html = _read_fixture("japan_dev_detail.html")

    respx.get("https://japan-dev.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    respx.get("https://japan-dev.com/security-jobs-in-japan").mock(
        return_value=httpx.Response(200, text=listing_html)
    )
    for detail_url in JapanDevScraper._extract_detail_urls(
        listing_html, "https://japan-dev.com/security-jobs-in-japan"
    ):
        respx.get(detail_url).mock(return_value=httpx.Response(200, text=detail_html))

    try:
        result = await scraper.scrape(since=datetime(2026, 9, 1, tzinfo=UTC))
    finally:
        await http.aclose()

    assert result.found == 10
    assert len(result.jobs) == 10
    assert result.errors == []
    assert all(j.source == "japan_dev" for j in result.jobs)
    assert all(j.role_category == "engineering" for j in result.jobs)
