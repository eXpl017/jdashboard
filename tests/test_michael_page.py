from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.config import Settings
from app.scrapers.base import ParseError
from app.scrapers.michael_page import MichaelPageScraper
from app.services.http import HttpClient

FIXTURES = "tests/fixtures"


def _read_fixture(name: str) -> str:
    with open(f"{FIXTURES}/{name}", encoding="utf-8") as f:
        return f.read()


@pytest.fixture()
def scraper() -> MichaelPageScraper:
    return MichaelPageScraper(http=None, settings=None)  # type: ignore[arg-type]


def test_michael_page_extracts_detail_urls(scraper):
    html = _read_fixture("michael_page_list.html")
    urls = MichaelPageScraper._extract_detail_urls(
        html, "https://www.michaelpage.co.jp/en/jobs/it-security"
    )

    # 24 unique job listings on the page (one link is a language-variant dup of
    # another); the apply-page link is ignored.
    assert len(urls) == 24
    for url in urls:
        assert url.startswith("https://www.michaelpage.co.jp/job-detail/")
        assert "ref/jn-" in url
        # Language variants collapse to a single canonical URL.
        assert "?lang=" not in url
        assert "/en/job-detail/" not in url

    # The two language variants of the security-engineer job collapse to one.
    canonical = "https://www.michaelpage.co.jp/job-detail/security-engineer/ref/jn-112026-7138331"
    assert urls.count(canonical) == 1


def test_michael_page_parses_detail(scraper):
    html = _read_fixture("michael_page_detail.html")
    url = "https://www.michaelpage.co.jp/job-detail/security-engineer/ref/jn-112026-7138331"
    job = MichaelPageScraper._parse_detail(scraper, html, url)

    assert job is not None
    assert job.source == "michael_page"
    assert job.source_job_id == "JN-112026-7138331"
    assert job.url == "https://www.michaelpage.co.jp/job-detail/security-engineer/ref/jn-112026-7138331"
    assert job.title == "Security Engineer"
    assert job.company == "Michael Page"
    assert job.location == "Tokyo"
    assert job.remote_type == "hybrid"  # HTML "Work from Home or Hybrid" wins
    assert job.employment_type == "full_time"
    assert (job.salary_min, job.salary_max, job.salary_currency) == (
        9_000_000,
        14_000_000,
        "JPY",
    )
    assert job.salary_text == "¥9,000,000 - ¥14,000,000 per year"
    assert job.posted_at_raw == "2026-11-02"
    assert job.posted_at == datetime(2026, 11, 1, 15, 0, tzinfo=UTC)
    assert job.language == "en"
    assert job.location_scope == "japan_hybrid"
    assert job.overseas_eligible is None
    assert job.role_category == "engineering"
    assert "security-engineering" in job.security_tags
    assert job.raw["jsonld"]["title"] == "Security Engineer"


def test_michael_page_detail_missing_jsonld_raises(scraper):
    with pytest.raises(ParseError):
        MichaelPageScraper._parse_detail(
            scraper, "<html><body>no json-ld</body></html>", "https://example.com/x"
        )


@pytest.mark.asyncio
@respx.mock
async def test_michael_page_full_scrape():
    settings = Settings(
        min_request_interval_seconds=0.0,
        max_retries=0,
        retry_backoff_seconds=0.0,
        request_timeout_seconds=5.0,
    )
    http = HttpClient(settings)
    scraper = MichaelPageScraper(http=http, settings=settings)

    listing_html = (
        "<html><body>"
        '<a href="/job-detail/security-engineer/ref/jn-112026-7138331">Security Engineer</a>'
        '<a href="/job-detail/csirt-analyst/ref/jn-102026-7128292">CSIRT Analyst</a>'
        '<a href="/job-detail/appsec-engineer/ref/jn-082026-7087088">AppSec Engineer</a>'
        "</body></html>"
    )
    detail_html = _read_fixture("michael_page_detail.html")

    respx.get("https://www.michaelpage.co.jp/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    respx.get("https://www.michaelpage.co.jp/en/jobs/it-security").mock(
        return_value=httpx.Response(200, text=listing_html)
    )
    respx.get(
        "https://www.michaelpage.co.jp/job-detail/security-engineer/ref/jn-112026-7138331"
    ).mock(return_value=httpx.Response(200, text=detail_html))
    respx.get(
        "https://www.michaelpage.co.jp/job-detail/csirt-analyst/ref/jn-102026-7128292"
    ).mock(return_value=httpx.Response(200, text=detail_html))
    respx.get(
        "https://www.michaelpage.co.jp/job-detail/appsec-engineer/ref/jn-082026-7087088"
    ).mock(return_value=httpx.Response(200, text=detail_html))

    try:
        result = await scraper.scrape(since=datetime(2026, 10, 1, tzinfo=UTC))
    finally:
        await http.aclose()

    assert result.found == 3
    assert len(result.jobs) == 3
    assert result.skipped == 0
    assert result.errors == []
    assert {j.source_job_id for j in result.jobs} == {
        "JN-112026-7138331",
        "JN-102026-7128292",
        "JN-082026-7087088",
    }
    assert all(j.source == "michael_page" for j in result.jobs)
    assert all(j.title == "Security Engineer" for j in result.jobs)
    assert all(j.role_category == "engineering" for j in result.jobs)
    assert all(j.location_scope == "japan_hybrid" for j in result.jobs)
