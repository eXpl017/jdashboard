import httpx
import pytest
import respx

from app.config import Settings
from app.scrapers.base import RateLimited, RobotsDisallowed, ScraperError
from app.services.http import HttpClient


def _settings(**overrides) -> Settings:
    defaults = {
        "min_request_interval_seconds": 0.0,
        "max_retries": 2,
        "retry_backoff_seconds": 0.0,
        "request_timeout_seconds": 5.0,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _allow_robots() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )


@respx.mock
@pytest.mark.asyncio
async def test_get_text_retries_on_500_then_succeeds():
    _allow_robots()
    route = respx.get("https://example.com/jobs/1").mock(
        side_effect=[httpx.Response(500), httpx.Response(200, text="ok")]
    )

    client = HttpClient(_settings())
    try:
        assert await client.get_text("https://example.com/jobs/1") == "ok"
        assert route.call_count == 2
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_rate_limited_after_retries():
    _allow_robots()
    respx.get("https://example.com/jobs/1").mock(return_value=httpx.Response(429))

    client = HttpClient(_settings(max_retries=1))
    try:
        with pytest.raises(RateLimited):
            await client.get_text("https://example.com/jobs/1")
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_robots_disallow_raises_without_fetching_page():
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /jobs")
    )

    client = HttpClient(_settings())
    try:
        with pytest.raises(RobotsDisallowed):
            await client.get_text("https://example.com/jobs/1")
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_robots_server_error_blocks_crawl():
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(503))

    client = HttpClient(_settings())
    try:
        with pytest.raises(RobotsDisallowed):
            await client.get_text("https://example.com/jobs/1")
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_not_found_raises_scraper_error():
    _allow_robots()
    respx.get("https://example.com/jobs/404").mock(return_value=httpx.Response(404))

    client = HttpClient(_settings())
    try:
        with pytest.raises(ScraperError):
            await client.get_text("https://example.com/jobs/404")
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_robots_cache_is_reused():
    robots_route = respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    respx.get("https://example.com/jobs/1").mock(
        return_value=httpx.Response(200, text="one")
    )
    respx.get("https://example.com/jobs/2").mock(
        return_value=httpx.Response(200, text="two")
    )

    client = HttpClient(_settings())
    try:
        await client.get_text("https://example.com/jobs/1")
        await client.get_text("https://example.com/jobs/2")
        assert robots_route.call_count == 1
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_per_host_throttle_sleeps_between_requests(monkeypatch):
    _allow_robots()
    respx.get("https://example.com/jobs/1").mock(
        return_value=httpx.Response(200, text="one")
    )
    respx.get("https://example.com/jobs/2").mock(
        return_value=httpx.Response(200, text="two")
    )

    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.services.http.asyncio.sleep", fake_sleep)

    client = HttpClient(_settings(min_request_interval_seconds=5.0))
    try:
        await client.get_text("https://example.com/jobs/1")
        await client.get_text("https://example.com/jobs/2")
    finally:
        await client.aclose()

    assert sleeps and sleeps[0] > 0
