from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.config import Settings
from app.scrapers.base import ParseError
from app.scrapers.daijob import DaijobScraper
from app.services.http import HttpClient

FIXTURES = "tests/fixtures"
CATEGORY_URL = (
    "https://www.daijob.com/en/jobs/search?js_jt%5B%5D=503&fl=1&pg=0"
)
SEARCH_RESULT_URL = (
    "https://www.daijob.com/en/jobs/search_result"
    "?job_types[]=503&job_search_form_hidden=1"
)
PAGE_2_URL = (
    "https://www.daijob.com/en/jobs/search_result"
    "?job_types[]=503&job_post_language=1&job_search_form_hidden=1&page=2"
)


def _read_fixture(name: str) -> str:
    with open(f"{FIXTURES}/{name}", encoding="utf-8") as f:
        return f.read()


@pytest.fixture()
def scraper() -> DaijobScraper:
    return DaijobScraper(http=None, settings=None)  # type: ignore[arg-type]


def test_daijob_extracts_detail_urls(scraper):
    html = _read_fixture("daijob_list.html")
    urls = DaijobScraper._extract_detail_urls(html, CATEGORY_URL)

    assert list(urls) == ["1001", "1002"]
    assert urls["1001"] == "https://www.daijob.com/en/jobs/detail/1001"
    assert urls["1002"] == "https://www.daijob.com/en/jobs/detail/1002"
    # Company, member, apply, and job-list links are ignored.
    assert all("/en/jobs/detail/" in url for url in urls.values())
    assert not any("/company/" in url for url in urls.values())
    assert not any("/member/" in url for url in urls.values())
    assert not any("/joblist/" in url for url in urls.values())


def test_daijob_pager_urls(scraper):
    html = _read_fixture("daijob_list.html")
    pages = DaijobScraper._pager_urls(html, CATEGORY_URL, max_pages=2)

    assert pages == [PAGE_2_URL]
    assert DaijobScraper._pager_urls(html, CATEGORY_URL, max_pages=1) == []


def test_daijob_parses_detail(scraper):
    html = _read_fixture("daijob_detail.html")
    url = "https://www.daijob.com/en/jobs/detail/1001"
    job = scraper._parse_detail(html, url)

    assert job is not None
    assert job.source == "daijob"
    assert job.source_job_id == "1001"
    assert job.url == url
    assert job.title == "Security Solutions Architect"
    assert job.company == "UST Japan"
    assert job.location == "Japan"
    assert job.remote_type == "unknown"
    assert job.employment_type == "full_time"
    assert (job.salary_min, job.salary_max, job.salary_currency) == (
        15_000_000,
        None,
        "JPY",
    )
    assert job.salary_text == "JPY - Japanese Yen JPY 15000K Over"
    assert job.posted_at_raw == "2026-11-10"
    assert job.posted_at == datetime(2026, 11, 9, 15, 0, tzinfo=UTC)
    assert job.source_updated_at == datetime(2026, 11, 9, 15, 0, tzinfo=UTC)
    assert job.expires_at == datetime(2027, 9, 6, 15, 0, tzinfo=UTC)
    assert job.japanese_level == "business"
    assert job.language == "en"
    assert job.location_scope == "japan_onsite"
    assert job.overseas_eligible is None
    assert job.role_category is not None


def test_daijob_parses_japanese_detail_without_jsonld(scraper):
    html = _read_fixture("daijob_detail_japanese.html")
    url = "https://www.daijob.com/en/jobs/detail/1002"
    job = scraper._parse_detail(html, url)

    assert job is not None
    assert job.source_job_id == "1002"
    assert job.title == "サイバーセキュリティエンジニア"
    assert job.company == "サンプル株式会社"
    assert job.location == "Tokyo, Minato"
    assert job.employment_type == "full_time"
    assert (job.salary_min, job.salary_max) == (6_000_000, 8_000_000)
    assert job.posted_at == datetime(2026, 11, 8, 15, 0, tzinfo=UTC)
    assert job.source_updated_at == datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
    assert job.japanese_level == "fluent"
    assert job.language == "ja"
    assert job.location_scope == "japan_onsite"
    assert job.role_category == "engineering"
    assert "security-engineering" in job.security_tags


def test_daijob_confidential_company_uses_recruiter(scraper):
    html = _read_fixture("daijob_detail.html").replace(
        '"name":"UST Japan"', '"name":"confidential"'
    ).replace(
        "<dd><span>UST Japan</span></dd>",
        "<dd><span>Company is not publicly visible</span></dd>",
    )
    job = scraper._parse_detail(
        html, "https://www.daijob.com/en/jobs/detail/1001"
    )

    assert job is not None
    assert job.company == "DcodingX Corporation"


def test_daijob_missing_title_raises(scraper):
    with pytest.raises(ParseError):
        scraper._parse_detail(
            "<html><body>no job</body></html>",
            "https://www.daijob.com/en/jobs/detail/9999",
        )


@pytest.mark.asyncio
@respx.mock
async def test_daijob_full_scrape_follows_redirect_and_deduplicates():
    settings = Settings(
        min_request_interval_seconds=0.0,
        max_retries=0,
        retry_backoff_seconds=0.0,
        request_timeout_seconds=5.0,
    )
    http = HttpClient(settings)
    scraper = DaijobScraper(http=http, settings=settings)

    listing_html = _read_fixture("daijob_list.html")
    page2_html = _read_fixture("daijob_list_page2.html")
    keyword_html = _read_fixture("daijob_keyword.html")
    detail_html = _read_fixture("daijob_detail.html")
    detail_ja_html = _read_fixture("daijob_detail_japanese.html")

    respx.get("https://www.daijob.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    respx.get(CATEGORY_URL).mock(
        return_value=httpx.Response(302, headers={"Location": SEARCH_RESULT_URL})
    )
    respx.get(SEARCH_RESULT_URL).mock(
        return_value=httpx.Response(200, text=listing_html)
    )
    respx.get(PAGE_2_URL).mock(
        return_value=httpx.Response(200, text=page2_html)
    )
    for keyword in DaijobScraper.keyword_searches:
        respx.get(DaijobScraper._keyword_url(keyword)).mock(
            return_value=httpx.Response(200, text=keyword_html)
        )

    for job_id in ("1001", "1003", "1004"):
        respx.get(f"https://www.daijob.com/en/jobs/detail/{job_id}").mock(
            return_value=httpx.Response(200, text=detail_html)
        )
    respx.get("https://www.daijob.com/en/jobs/detail/1002").mock(
        return_value=httpx.Response(200, text=detail_ja_html)
    )

    try:
        result = await scraper.scrape(since=datetime(2026, 10, 1, tzinfo=UTC))
    finally:
        await http.aclose()

    # 1001 appears in both the category and keyword results but is fetched once.
    assert result.found == 4
    assert len(result.jobs) == 4
    assert result.errors == []
    assert {job.url for job in result.jobs} == {
        f"https://www.daijob.com/en/jobs/detail/{job_id}"
        for job_id in ("1001", "1002", "1003", "1004")
    }
    assert all(job.source == "daijob" for job in result.jobs)


@pytest.mark.asyncio
@respx.mock
async def test_daijob_respects_detail_request_cap():
    settings = Settings(
        min_request_interval_seconds=0.0,
        max_retries=0,
        retry_backoff_seconds=0.0,
        request_timeout_seconds=5.0,
    )
    http = HttpClient(settings)
    scraper = DaijobScraper(http=http, settings=settings)
    scraper.max_detail_requests = 2

    listing_html = _read_fixture("daijob_list.html")
    detail_html = _read_fixture("daijob_detail.html")

    respx.get("https://www.daijob.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    respx.get(CATEGORY_URL).mock(
        return_value=httpx.Response(200, text=listing_html)
    )
    respx.get(PAGE_2_URL).mock(
        return_value=httpx.Response(200, text=_read_fixture("daijob_list_page2.html"))
    )
    for keyword in DaijobScraper.keyword_searches:
        respx.get(DaijobScraper._keyword_url(keyword)).mock(
            return_value=httpx.Response(200, text=_read_fixture("daijob_keyword.html"))
        )
    for job_id in ("1001", "1002", "1003", "1004"):
        respx.get(f"https://www.daijob.com/en/jobs/detail/{job_id}").mock(
            return_value=httpx.Response(200, text=detail_html)
        )

    try:
        result = await scraper.scrape(since=datetime(2026, 10, 1, tzinfo=UTC))
    finally:
        await http.aclose()

    assert result.found == 4
    assert len(result.jobs) == 2
