import logging
import re
from datetime import datetime
from typing import ClassVar
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ParseError, ScrapedJob, ScraperError, ScrapeResult
from app.services.classify import classify
from app.services.dates import parse_date_only, to_utc
from app.services.jsonld import extract_job_posting_jsonld
from app.services.normalize import (
    canonical_url,
    detect_employment_type,
    detect_language,
    detect_location_scope,
    detect_overseas_eligible,
    detect_remote,
    strip_html,
)

logger = logging.getLogger(__name__)

# Matches a job-detail anchor href, capturing the jn- reference id.
_REF_JN_RE = re.compile(r"ref/jn-([A-Za-z0-9_-]+)", re.I)
_LANG_PREFIX_RE = re.compile(r"^/(en|ja)/(.*)$")


def _strip_lang_prefix(url: str) -> str:
    """Remove a leading ``/en/`` or ``/ja/`` language prefix so the same job
    has a stable canonical URL/fingerprint regardless of language variant."""
    parsed = urlsplit(url)
    match = _LANG_PREFIX_RE.match(parsed.path)
    if match:
        path = "/" + match.group(2)
    else:
        path = parsed.path
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), path, "", ""))


class MichaelPageScraper(BaseScraper):
    source_id = "michael_page"
    source_name = "Michael Page Japan"
    listing_url = "https://www.michaelpage.co.jp/en/jobs/it-security"
    max_detail_requests: ClassVar[int] = 25
    is_security_category = True

    async def scrape(self, since: datetime) -> ScrapeResult:
        """Fetch the IT Security listing, then parse each detail page."""
        try:
            listing_html = await self.http.get_text(self.listing_url)
        except Exception as exc:  # pragma: no cover - network failure is source-wide
            raise ScraperError(
                f"Failed to fetch Michael Page listing {self.listing_url}: {exc}"
            ) from exc

        detail_urls = self._extract_detail_urls(listing_html, self.listing_url)
        found = len(detail_urls)

        jobs: list[ScrapedJob] = []
        skipped = 0
        errors: list[str] = []

        for detail_url in detail_urls[: self.max_detail_requests]:
            try:
                detail_html = await self.http.get_text(detail_url)
            except Exception as exc:
                errors.append(f"{detail_url}: {exc}")
                logger.warning(
                    "Michael Page detail fetch failed %s: %s", detail_url, exc
                )
                continue
            try:
                job = self._parse_detail(detail_html, detail_url)
            except ParseError as exc:
                errors.append(f"{detail_url}: {exc}")
                logger.warning(
                    "Michael Page detail parse failed %s: %s", detail_url, exc
                )
                continue
            if job is None:
                skipped += 1
                continue
            if job.posted_at is not None and job.posted_at < since:
                skipped += 1
                continue
            jobs.append(job)

        return ScrapeResult(
            source=self.source_id,
            jobs=jobs,
            found=found,
            skipped=skipped,
            errors=errors,
        )

    @staticmethod
    def _extract_detail_urls(listing_html: str, base_url: str) -> list[str]:
        """Return unique, canonical absolute detail URLs, deduped by jn- ref."""
        soup = BeautifulSoup(listing_html, "lxml")
        seen: dict[str, str] = {}
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if "/job-detail/" not in href:
                continue
            match = _REF_JN_RE.search(href)
            if not match:
                continue
            ref_id = match.group(1)
            absolute = urljoin(base_url, href)
            normalized = canonical_url(_strip_lang_prefix(absolute))
            seen.setdefault(ref_id, normalized)
        return list(seen.values())

    def _parse_detail(self, detail_html: str, detail_url: str) -> ScrapedJob | None:
        jsonld = extract_job_posting_jsonld(detail_html)
        if jsonld is None:
            raise ParseError(f"No JSON-LD JobPosting on {detail_url}")

        title = (jsonld.get("title") or "").strip()
        if not title:
            raise ParseError(f"Missing job title on {detail_url}")

        description_html = jsonld.get("description") or ""
        description_text = strip_html(description_html)

        posted_at_raw = jsonld.get("datePosted")
        posted_at = to_utc(parse_date_only(posted_at_raw)) if posted_at_raw else None

        hiring_org = jsonld.get("hiringOrganization") or {}
        company = (hiring_org.get("name") or "Michael Page").strip() or "Michael Page"

        employment_type = detect_employment_type(jsonld.get("employmentType") or "")

        job_location = (jsonld.get("jobLocation") or {}).get("address") or {}
        location = job_location.get("addressLocality")

        base_salary = jsonld.get("baseSalary") or {}
        salary_value = base_salary.get("value") or {}
        salary_min = self._parse_int(salary_value.get("minValue"))
        salary_max = self._parse_int(salary_value.get("maxValue"))
        salary_currency = base_salary.get("currency") or "JPY"
        salary_text = None
        if salary_min is not None and salary_max is not None:
            salary_text = f"¥{salary_min:,} - ¥{salary_max:,} per year"

        # HTML-derived fields are more granular than JSON-LD; prefer them.
        html_fields = self._parse_detail_html(detail_html)
        remote_type = html_fields["remote_type"] or self._remote_type_from_jsonld(
            jsonld
        ) or "unknown"
        salary_text = html_fields["salary_text"] or salary_text

        source_job_id = self._extract_source_job_id(detail_url)

        language = detect_language(title, description_text)
        location_scope = detect_location_scope(location, remote_type, description_text)
        overseas_eligible = detect_overseas_eligible(description_text)

        classification = classify(
            title,
            description_text,
            source_tags=[],
            source_is_security_category=self.is_security_category,
        )

        return ScrapedJob(
            source=self.source_id,
            source_job_id=source_job_id,
            url=canonical_url(detail_url),
            title=title,
            company=company,
            location=location,
            remote_type=remote_type,
            employment_type=employment_type,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            salary_text=salary_text,
            description_text=description_text,
            description_html=description_html or None,
            posted_at=posted_at,
            posted_at_raw=posted_at_raw,
            language=language,
            location_scope=location_scope,
            overseas_eligible=overseas_eligible,
            security_tags=classification.tags,
            role_category=classification.role_category,
            raw={"jsonld": jsonld},
        )

    @staticmethod
    def _parse_detail_html(detail_html: str) -> dict[str, str | None]:
        """Extract granular fields from the detail-page HTML summary block."""
        soup = BeautifulSoup(detail_html, "lxml")
        remote_type: str | None = None
        salary_text: str | None = None

        job_nature = soup.select_one("span.job-nature")
        if job_nature:
            remote_type = detect_remote(job_nature.get_text(" ", strip=True))

        job_salary = soup.select_one("span.job-salary")
        if job_salary:
            salary_text = job_salary.get_text(" ", strip=True)

        return {"remote_type": remote_type, "salary_text": salary_text}

    @staticmethod
    def _remote_type_from_jsonld(jsonld: dict) -> str | None:
        job_location_type = (jsonld.get("jobLocationType") or "").upper()
        if job_location_type == "TELECOMMUTE":
            return "remote"
        return None

    @staticmethod
    def _extract_source_job_id(detail_url: str) -> str | None:
        match = _REF_JN_RE.search(detail_url)
        if match:
            return f"JN-{match.group(1)}"
        return None

    @staticmethod
    def _parse_int(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value).replace(",", ""))
        except (ValueError, TypeError):
            return None
