from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from app.config import Settings
    from app.services.http import HttpClient


class ScraperError(Exception):
    """Base class for source-wide scraper failures with user-safe messages."""


class RobotsDisallowed(ScraperError):
    """robots.txt forbids fetching the listing or detail page."""


class SourceChanged(ScraperError):
    """The source layout changed and the parser can no longer find jobs."""


class RateLimited(ScraperError):
    """The source kept returning 429 after the configured retries."""


class ParseError(ScraperError):
    """A single page could not be parsed into a usable job."""


@dataclass(slots=True)
class ScrapedJob:
    source: str
    url: str
    title: str
    source_job_id: str | None = None
    company: str | None = None
    location: str | None = None
    remote_type: str | None = None
    employment_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "JPY"
    salary_text: str | None = None
    description_text: str | None = None
    description_html: str | None = None
    posted_at: datetime | None = None
    posted_at_raw: str | None = None
    source_updated_at: datetime | None = None
    expires_at: datetime | None = None
    japanese_level: str | None = None
    visa_sponsorship: str | None = None
    overseas_eligible: bool | None = None
    role_category: str | None = None
    language: str | None = None
    location_scope: str | None = None
    security_tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScrapeResult:
    source: str
    jobs: list[ScrapedJob] = field(default_factory=list)
    found: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class BaseScraper:
    """Shared contract: fetch, parse, normalize, return jobs. Never writes to the DB."""

    source_id: ClassVar[str]
    source_name: ClassVar[str]
    listing_url: ClassVar[str]
    max_detail_requests: ClassVar[int] = 40
    is_security_category: ClassVar[bool] = False

    def __init__(self, http: "HttpClient", settings: "Settings") -> None:
        self.http = http
        self.settings = settings

    async def scrape(self, since: datetime) -> ScrapeResult:
        """Return jobs posted or updated since ``since`` (UTC)."""
        raise NotImplementedError
