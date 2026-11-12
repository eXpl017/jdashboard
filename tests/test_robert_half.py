from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.config import Settings
from app.scrapers.base import SourceChanged
from app.scrapers.robert_half import RobertHalfScraper
from app.services.http import HttpClient

FIXTURES = "tests/fixtures"
LIST_URL = "https://www.roberthalf.com/jp/en/jobs"
PAGE_2_URL = f"{LIST_URL}?pagenumber=2"
DETAIL_URL_SOC = (
    "https://www.roberthalf.com/jp/en/job/tokyo/soc-analyst/06940-0000000004-jpen"
)
DETAIL_URL_INCIDENT = (
    "https://www.roberthalf.com/jp/en/job/tokyo/incident-response-analyst/"
    "06940-0000000005-jpen"
)


def _read_fixture(name: str) -> str:
    with open(f"{FIXTURES}/{name}", encoding="utf-8") as f:
        return f.read()


@pytest.fixture()
def scraper() -> RobertHalfScraper:
    return RobertHalfScraper(http=None, settings=None)  # type: ignore[arg-type]


def _listing_jobs(scraper: RobertHalfScraper) -> list[dict]:
    data = RobertHalfScraper._extract_initial_results(
        _read_fixture("robert_half_list.html")
    )
    return data["jobs"]


def test_robert_half_extracts_initial_results(scraper):
    data = RobertHalfScraper._extract_initial_results(
        _read_fixture("robert_half_list.html")
    )

    assert len(data["jobs"]) == 5
    assert data["jobs"][0]["jobtitle"] == "Security Engineer"


def test_robert_half_unescapes_javascript_string():
    raw = (
        r"{\x22title\x22:\x22Cloud\u002DSecurity\x22,"
        r"\x22path\x22:\x22a\/b\x22,\x22quote\x22:\x27ok\x27}"
    )

    assert RobertHalfScraper._js_string_unescape(raw) == (
        '{"title":"Cloud-Security","path":"a/b","quote":\'ok\'}'
    )


def test_robert_half_unescapes_surrogate_pairs():
    assert RobertHalfScraper._js_string_unescape(r"\uD83D\uDE00") == "😀"


def test_robert_half_parses_listing_job(scraper):
    job = scraper._parse_listing_job(_listing_jobs(scraper)[0])

    assert job.source == "robert_half"
    assert job.source_job_id == "06940-0000000001"
    assert job.url == (
        "https://www.roberthalf.com/jp/en/job/tokyo/security-engineer/"
        "06940-0000000001-jpen"
    )
    assert job.title == "Security Engineer"
    assert job.company == "Robert Half Japan"
    assert job.location == "Tokyo, Japan"
    assert job.remote_type == "remote"
    assert job.employment_type == "full_time"
    assert (job.salary_min, job.salary_max, job.salary_currency) == (
        8_000_000,
        14_000_000,
        "JPY",
    )
    assert job.salary_text == "¥8,000,000 - ¥14,000,000 per year"
    assert job.posted_at_raw == "2026-11-10T08:00:00Z"
    assert job.posted_at == datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
    assert job.expires_at == datetime(2027, 2, 8, 8, 0, tzinfo=UTC)
    assert job.language == "en"
    assert job.location_scope == "japan_remote"
    assert job.overseas_eligible is None
    assert job.role_category == "engineering"
    assert "security-engineering" in job.security_tags


def test_robert_half_parses_japanese_listing_job(scraper):
    job = scraper._parse_listing_job(_listing_jobs(scraper)[1])

    assert job.title == "IT Security Consultant (GRC)"
    assert job.remote_type == "hybrid"
    assert job.employment_type == "contract"
    assert (job.salary_min, job.salary_max) == (17_000_000, 17_000_000)
    assert job.salary_text == "¥17,000,000 per year"
    assert job.posted_at == datetime(2026, 11, 9, 7, 25, tzinfo=UTC)
    assert job.language in ("ja", "bilingual")
    assert job.location_scope == "japan_hybrid"
    assert job.role_category == "consulting"


def test_robert_half_does_not_mark_non_japan_roles_as_japan(scraper):
    job = scraper._parse_listing_job(_listing_jobs(scraper)[2])

    assert job.title == "Cloud Security Architect"
    assert job.location == "Singapore, SG"
    assert job.remote_type == "remote"
    assert job.location_scope == "international_remote"
    assert job.location_scope != "japan_remote"


def test_robert_half_strips_tracking_images(scraper):
    raw_job = dict(_listing_jobs(scraper)[0])
    raw_job["description"] = (
        '<p>Build secure systems.</p><img src="https://counter.example/pixel.gif">'
    )

    job = scraper._parse_listing_job(raw_job)

    assert job.description_text == "Build secure systems."
    assert job.description_html == "<p>Build secure systems.</p>"
    assert "<img" not in job.description_html
    assert "counter.example" not in job.description_html


def test_robert_half_handles_missing_salary_and_short_description(scraper):
    job = scraper._parse_listing_job(_listing_jobs(scraper)[3])

    assert job.title == "SOC Analyst"
    assert job.salary_min is None
    assert job.salary_max is None
    assert job.salary_text is None  # never invent a missing salary
    assert job.employment_type == "contract"
    assert job.role_category == "operations"
    assert job.description_text == "Short summary"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("8.0M", 8_000_000),
        ("14.0M", 14_000_000),
        ("15000K", 15_000_000),
        ("1,200", 1_200),
        ("", None),
        (None, None),
        ("not a number", None),
    ],
)
def test_robert_half_parses_payrate(value, expected):
    assert RobertHalfScraper._parse_payrate(value) == expected


def test_robert_half_missing_initial_results_raises():
    with pytest.raises(SourceChanged):
        RobertHalfScraper._extract_initial_results(
            "<html><body>no payload here</body></html>"
        )


def _settings() -> Settings:
    return Settings(
        min_request_interval_seconds=0.0,
        max_retries=0,
        retry_backoff_seconds=0.0,
        request_timeout_seconds=5.0,
    )


def _mock_listing_and_details() -> tuple[respx.Route, respx.Route, respx.Route, respx.Route]:
    respx.get(url__eq="https://www.roberthalf.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    page1 = respx.get(url__eq=LIST_URL).mock(
        return_value=httpx.Response(
            200, text=_read_fixture("robert_half_list.html")
        )
    )
    page2 = respx.get(url__eq=PAGE_2_URL).mock(
        return_value=httpx.Response(
            200, text=_read_fixture("robert_half_list_page2.html")
        )
    )
    detail = _read_fixture("robert_half_detail.html")
    detail_soc = respx.get(url__eq=DETAIL_URL_SOC).mock(
        return_value=httpx.Response(200, text=detail)
    )
    detail_incident = respx.get(url__eq=DETAIL_URL_INCIDENT).mock(
        return_value=httpx.Response(200, text=detail)
    )
    return page1, page2, detail_soc, detail_incident


@pytest.mark.asyncio
@respx.mock
async def test_robert_half_stops_pagination_at_cutoff():
    settings = _settings()
    http = HttpClient(settings)
    scraper = RobertHalfScraper(http=http, settings=settings)
    page1, page2, detail_soc, detail_incident = _mock_listing_and_details()

    try:
        result = await scraper.scrape(since=datetime(2026, 11, 1, tzinfo=UTC))
    finally:
        await http.aclose()

    assert result.found == 7
    assert result.skipped == 2
    assert len(result.jobs) == 5
    assert result.errors == []
    assert page1.call_count == 1
    assert page2.call_count == 1
    # A third page is never requested; respx would raise on the unmatched URL.
    assert detail_soc.call_count == 1
    assert detail_incident.call_count == 1

    soc = next(job for job in result.jobs if job.title == "SOC Analyst")
    assert soc.description_text is not None
    assert "24/7 SOC" in soc.description_text


@pytest.mark.asyncio
@respx.mock
async def test_robert_half_detail_fetch_is_capped():
    settings = _settings()
    http = HttpClient(settings)
    scraper = RobertHalfScraper(http=http, settings=settings)
    scraper.max_detail_requests = 1
    page1, page2, detail_soc, detail_incident = _mock_listing_and_details()

    try:
        result = await scraper.scrape(since=datetime(2026, 11, 1, tzinfo=UTC))
    finally:
        await http.aclose()

    assert len(result.jobs) == 5
    assert detail_soc.call_count == 1
    assert detail_incident.call_count == 0

    soc = next(job for job in result.jobs if job.title == "SOC Analyst")
    incident = next(
        job for job in result.jobs if job.title == "Incident Response Analyst"
    )
    assert soc.description_text is not None
    assert "24/7 SOC" in soc.description_text
    # The second short listing falls back to its summary when the cap is hit.
    assert incident.description_text == "Investigate alerts and support incident response."
