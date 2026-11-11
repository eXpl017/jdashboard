import asyncio
import logging
import random
import time
from typing import Any
from urllib.robotparser import RobotFileParser

import httpx

from app.config import Settings
from app.scrapers.base import ParseError, RateLimited, RobotsDisallowed, ScraperError

logger = logging.getLogger(__name__)


class HttpClient:
    """Polite async HTTP wrapper shared by every scraper.

    Responsibilities: identify itself, follow redirects, apply per-host delays,
    retry transient failures with backoff, cache robots.txt, and raise typed
    scraper errors. It never bypasses a robots.txt disallow.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client or httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": settings.user_agent},
        )
        self._robots: dict[str, RobotFileParser] = {}
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._last_request: dict[str, float] = {}
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    def semaphore(self, name: str) -> asyncio.Semaphore:
        """Return a per-source semaphore to bound concurrent detail requests."""
        if name not in self._semaphores:
            self._semaphores[name] = asyncio.Semaphore(
                max(self.settings.max_detail_concurrency, 1)
            )
        return self._semaphores[name]

    async def get_text(self, url: str) -> str:
        response = await self._get(url)
        return response.text

    async def get_json(self, url: str) -> Any:
        response = await self._get(url)
        try:
            return response.json()
        except ValueError as exc:
            raise ParseError(f"Invalid JSON from {url}") from exc

    async def _get(self, url: str) -> httpx.Response:
        await self._check_robots(url)
        await self._throttle(url)
        return await self._request_with_retries(url)

    async def _check_robots(self, url: str) -> None:
        parser = await self._robots_parser(url)
        if not parser.can_fetch(self.settings.user_agent, url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")

    async def _robots_parser(self, url: str) -> RobotFileParser:
        parts = httpx.URL(url)
        origin = f"{parts.scheme}://{parts.netloc.decode('ascii')}"
        if origin in self._robots:
            return self._robots[origin]

        parser = RobotFileParser()
        parser.set_url(f"{origin}/robots.txt")
        try:
            response = await self._client.get(f"{origin}/robots.txt")
            if response.status_code < 400:
                try:
                    parser.parse(response.text.splitlines())
                except ValueError:
                    parser.allow_all = True
            elif response.status_code >= 500:
                # RFC 9309: an unreachable robots.txt means assume disallow.
                parser.disallow_all = True
            else:
                # A 4xx response (usually 404) means no restrictions.
                parser.allow_all = True
        except httpx.HTTPError as exc:
            logger.warning("Could not read robots.txt for %s: %s", origin, exc)
            parser.disallow_all = True

        self._robots[origin] = parser
        return parser

    async def _throttle(self, url: str) -> None:
        host = httpx.URL(url).host or ""
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            interval = self.settings.min_request_interval_seconds
            if interval > 0:
                last = self._last_request.get(host)
                if last is not None:
                    delay = interval - (time.monotonic() - last)
                    if delay > 0:
                        await asyncio.sleep(delay)
            self._last_request[host] = time.monotonic()

    async def _request_with_retries(self, url: str) -> httpx.Response:
        attempts = max(self.settings.max_retries, 0) + 1
        for attempt in range(attempts):
            try:
                response = await self._client.get(url)
            except httpx.TimeoutException as exc:
                if attempt == attempts - 1:
                    raise ScraperError(f"Timed out fetching {url}") from exc
                await self._sleep_backoff(attempt)
                continue
            except httpx.HTTPError as exc:
                if attempt == attempts - 1:
                    raise ScraperError(f"Failed to fetch {url}: {exc}") from exc
                await self._sleep_backoff(attempt)
                continue

            if response.status_code == 429:
                if attempt == attempts - 1:
                    raise RateLimited(f"Rate limited while fetching {url}")
                await self._sleep_backoff(attempt, response.headers.get("Retry-After"))
                continue
            if 500 <= response.status_code < 600:
                if attempt == attempts - 1:
                    raise ScraperError(
                        f"Server error {response.status_code} while fetching {url}"
                    )
                await self._sleep_backoff(attempt)
                continue

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ScraperError(
                    f"HTTP {response.status_code} while fetching {url}"
                ) from exc
            return response

        raise ScraperError(f"Failed to fetch {url}")

    async def _sleep_backoff(self, attempt: int, retry_after: str | None = None) -> None:
        delay = self.settings.retry_backoff_seconds * (2**attempt)
        if retry_after:
            try:
                delay = max(delay, float(retry_after))
            except ValueError:
                pass
        if delay <= 0:
            return
        # Add jitter so parallel sources do not retry in lockstep.
        await asyncio.sleep(delay + random.uniform(0, 0.25))
