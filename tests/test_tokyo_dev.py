from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.config import Settings
from app.scrapers.base import ParseError
from app.scrapers.tokyo_dev import TokyoDevScraper
from app.services.http import HttpClient

FIXTURES = "tests/fixtures"


def _read_fixture(name: str) -> str:
    with open(f"{FIXTURES}/{name}", encoding="utf-8") as f:
        return f.read()


@pytest.fixture()
def scraper() -> TokyoDevScraper:
    return TokyoDevScraper(http=None, settings=None)  # type: ignore[arg-type]


def test_tokyo_dev_extracts_detail_urls(scraper):
    html = _read_fixture("tokyo_dev_list.html")
    urls = TokyoDevScraper._extract_detail_urls(
        html, "https://www.tokyodev.com/jobs/security"
    )

    assert len(urls) == 4
    assert all(url.startswith("https://www.tokyodev.com/companies/") for url in urls)
    assert all("/jobs/" in url for url in urls)
    # Company, navigation, and apply/question links are ignored.
    assert not any(url.endswith("/jobs") for url in urls)
    assert not any("/c/" in url for url in urls)
    assert not any(url.endswith("/questions/new") for url in urls)


def test_tokyo_dev_parses_detail(scraper):
    html = _read_fixture("tokyo_dev_detail.html")
    url = "https://www.tokyodev.com/companies/moneyforward/jobs/ai-security-engineer-ciso-office-tokyo"
    job = TokyoDevScraper._parse_detail(scraper, html, url)

    assert job is not None
    assert job.source == "tokyo_dev"
    assert job.source_job_id == "2359"
    assert job.url == url
    assert job.title == "AI Security Engineer, CISO Office, Tokyo"
    assert job.company == "Money Forward"
    assert job.location == "Minato-ku, Tokyo"
    assert job.remote_type == "hybrid"
    assert job.employment_type == "full_time"
    assert (job.salary_min, job.salary_max, job.salary_currency) == (
        6_900_000,
        17_004_000,
        "JPY",
    )
    assert job.salary_text == "¥6,900,000 - ¥17,004,000 per year"
    assert job.posted_at_raw == "2026-11-02T17:26:25.347+09:00"
    assert job.posted_at == datetime(2026, 11, 2, 8, 26, 25, 347000, tzinfo=UTC)
    assert job.source_updated_at == datetime(2026, 11, 11, 15, 0, tzinfo=UTC)
    assert job.japanese_level == "conversational"
    assert job.language == "en"
    assert job.location_scope == "japan_hybrid"
    assert job.overseas_eligible is True
    # "CISO Office" is classified as management by the shared title-first rules.
    assert job.role_category == "management"
    assert "security-engineering" in job.security_tags
    assert "ciso" in job.security_tags


def test_tokyo_dev_residents_only_and_missing_salary(scraper):
    html = _read_fixture("tokyo_dev_detail_residents.html")
    url = "https://www.tokyodev.com/companies/hennge/jobs/corporate-it-security-specialist"
    job = TokyoDevScraper._parse_detail(scraper, html, url)

    assert job is not None
    assert job.source_job_id == "2213"
    assert job.company == "HENNGE"
    assert job.salary_min is None
    assert job.salary_max is None
    assert job.salary_text is None  # never invent a missing salary
    assert job.remote_type == "hybrid"
    assert job.overseas_eligible is False
    assert job.japanese_level == "business"
    assert job.posted_at == datetime(2026, 7, 5, 23, 50, 55, 482000, tzinfo=UTC)
    assert job.role_category == "engineering"
    assert "grc" in job.security_tags


def test_tokyo_dev_missing_jsonld_raises(scraper):
    with pytest.raises(ParseError):
        TokyoDevScraper._parse_detail(
            scraper, "<html><body>no json-ld</body></html>", "https://example.com/x"
        )


def test_tokyo_dev_atom_fallback(scraper):
    xml = _read_fixture("tokyo_dev_atom.xml")

    all_urls = TokyoDevScraper._extract_atom_urls(
        xml, "https://www.tokyodev.com/jobs/atom.xml"
    )
    assert len(all_urls) == 3

    recent = TokyoDevScraper._extract_atom_urls(
        xml,
        "https://www.tokyodev.com/jobs/atom.xml",
        since=datetime(2026, 10, 1, tzinfo=UTC),
    )
    assert len(recent) == 2
    assert not any("stale-job" in url for url in recent)


@pytest.mark.asyncio
@respx.mock
async def test_tokyo_dev_full_scrape():
    settings = Settings(
        min_request_interval_seconds=0.0,
        max_retries=0,
        retry_backoff_seconds=0.0,
        request_timeout_seconds=5.0,
    )
    http = HttpClient(settings)
    scraper = TokyoDevScraper(http=http, settings=settings)

    listing_html = _read_fixture("tokyo_dev_list.html")
    detail_html = _read_fixture("tokyo_dev_detail.html")

    respx.get("https://www.tokyodev.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    respx.get("https://www.tokyodev.com/jobs/security").mock(
        return_value=httpx.Response(200, text=listing_html)
    )
    for detail_url in TokyoDevScraper._extract_detail_urls(
        listing_html, "https://www.tokyodev.com/jobs/security"
    ):
        respx.get(detail_url).mock(return_value=httpx.Response(200, text=detail_html))

    try:
        result = await scraper.scrape(since=datetime(2026, 10, 1, tzinfo=UTC))
    finally:
        await http.aclose()

    assert result.found == 4
    assert len(result.jobs) == 4
    assert result.errors == []
    assert all(j.source == "tokyo_dev" for j in result.jobs)
    assert all(j.role_category is not None for j in result.jobs)


@pytest.mark.asyncio
@respx.mock
async def test_tokyo_dev_atom_fallback_scrape():
    settings = Settings(
        min_request_interval_seconds=0.0,
        max_retries=0,
        retry_backoff_seconds=0.0,
        request_timeout_seconds=5.0,
    )
    http = HttpClient(settings)
    scraper = TokyoDevScraper(http=http, settings=settings)

    atom_xml = _read_fixture("tokyo_dev_atom.xml")
    detail_html = _read_fixture("tokyo_dev_detail.html")

    respx.get("https://www.tokyodev.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    respx.get("https://www.tokyodev.com/jobs/security").mock(
        return_value=httpx.Response(200, text="<html><body>no jobs</body></html>")
    )
    respx.get("https://www.tokyodev.com/jobs/atom.xml").mock(
        return_value=httpx.Response(200, text=atom_xml)
    )
    for detail_url in TokyoDevScraper._extract_atom_urls(
        atom_xml,
        "https://www.tokyodev.com/jobs/atom.xml",
        since=datetime(2026, 10, 1, tzinfo=UTC),
    ):
        respx.get(detail_url).mock(return_value=httpx.Response(200, text=detail_html))

    try:
        result = await scraper.scrape(since=datetime(2026, 10, 1, tzinfo=UTC))
    finally:
        await http.aclose()

    assert result.found == 2
    assert len(result.jobs) == 2
    assert result.errors == []
