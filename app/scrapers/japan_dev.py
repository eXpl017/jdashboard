import logging
import re
from datetime import datetime
from typing import ClassVar
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ParseError, ScrapedJob, ScraperError, ScrapeResult
from app.services.classify import classify
from app.services.dates import parse_date_only, to_utc
from app.services.jsonld import extract_job_posting_jsonld
from app.services.normalize import (
    canonical_url,
    detect_language,
    detect_location_scope,
    detect_remote,
    strip_html,
)

logger = logging.getLogger(__name__)

# Matches JapanDev job links: /jobs/<company>/<slug>-<id>
_JOB_LINK_RE = re.compile(r"^/jobs/[^/]+/[^/]+-[A-Za-z0-9]{6,}$")
_REF_ID_RE = re.compile(r"-([A-Za-z0-9]{6,})$")


class JapanDevScraper(BaseScraper):
    source_id = "japan_dev"
    source_name = "JapanDev"
    listing_url = "https://japan-dev.com/security-jobs-in-japan"
    max_detail_requests: ClassVar[int] = 40
    is_security_category = True

    async def scrape(self, since: datetime) -> ScrapeResult:
        try:
            listing_html = await self.http.get_text(self.listing_url)
        except Exception as exc:
            raise ScraperError(
                f"Failed to fetch JapanDev listing {self.listing_url}: {exc}"
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
                logger.warning("JapanDev detail fetch failed %s: %s", detail_url, exc)
                continue
            try:
                job = self._parse_detail(detail_html, detail_url)
            except ParseError as exc:
                errors.append(f"{detail_url}: {exc}")
                logger.warning("JapanDev detail parse failed %s: %s", detail_url, exc)
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
        soup = BeautifulSoup(listing_html, "lxml")
        seen: dict[str, str] = {}
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if not _JOB_LINK_RE.match(href):
                continue
            absolute = urljoin(base_url, href)
            normalized = canonical_url(absolute)
            # Use the trailing id as the dedup key.
            match = _REF_ID_RE.search(href)
            key = match.group(1) if match else normalized
            seen.setdefault(key, normalized)
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

        expires_at_raw = jsonld.get("validThrough")
        expires_at = to_utc(parse_date_only(expires_at_raw)) if expires_at_raw else None

        hiring_org = jsonld.get("hiringOrganization") or {}
        company = (hiring_org.get("name") or "").strip() or "JapanDev"

        employment_type = self._detect_employment_type(jsonld.get("employmentType") or "")

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

        remote_type = self._detect_remote(detail_html)

        source_job_id = self._extract_source_job_id(detail_url)

        language = detect_language(title, description_text)
        location_scope = detect_location_scope(location, remote_type, description_text)

        overseas_eligible = self._detect_overseas_eligible(jsonld)

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
            source_updated_at=expires_at,
            expires_at=expires_at,
            language=language,
            location_scope=location_scope,
            overseas_eligible=overseas_eligible,
            security_tags=classification.tags,
            role_category=classification.role_category,
            raw={"jsonld": jsonld},
        )

    @staticmethod
    def _detect_remote(detail_html: str) -> str:
        soup = BeautifulSoup(detail_html, "lxml")
        remote_el = soup.select_one(".job-detail__remote")
        if remote_el:
            return detect_remote(remote_el.get_text(" ", strip=True))
        return "unknown"

    @staticmethod
    def _detect_overseas_eligible(jsonld: dict) -> bool | None:
        requirements = jsonld.get("applicantLocationRequirements") or []
        if not requirements:
            return None
        countries = {
            req.get("name")
            for req in requirements
            if isinstance(req, dict) and req.get("name")
        }
        if not countries:
            return None
        # Japan-only listings restrict to JP; anything broader means overseas OK.
        if countries == {"JP"}:
            return False
        if "JP" in countries and len(countries) > 1:
            return True
        # Worldwide / no JP restriction => overseas eligible.
        return True

    @staticmethod
    def _detect_employment_type(value: str) -> str:
        lowered = value.lower()
        if "full" in lowered:
            return "full_time"
        if "contract" in lowered:
            return "contract"
        if "part" in lowered:
            return "part_time"
        if "intern" in lowered:
            return "internship"
        return "unknown"

    @staticmethod
    def _extract_source_job_id(detail_url: str) -> str | None:
        match = _REF_ID_RE.search(detail_url)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _parse_int(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value).replace(",", ""))
        except (ValueError, TypeError):
            return None
