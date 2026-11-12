import json
import logging
import re
from datetime import datetime
from typing import Any, ClassVar

from bs4 import BeautifulSoup

from app.scrapers.base import (
    BaseScraper,
    ParseError,
    ScrapedJob,
    ScraperError,
    ScrapeResult,
    SourceChanged,
)
from app.services.classify import classify
from app.services.dates import parse_iso_datetime, to_utc
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

# The listing is an AEM page with an escaped JSON string assigned to a global.
_INITIAL_RESULTS_RE = re.compile(
    r"initialResults\s*=\s*JSON\.parse\('(.*?)'\);", re.DOTALL
)
_JOB_DETAILS_RE = re.compile(r"jobDetails\s*=\s*JSON\.parse\('(.*?)'\);", re.DOTALL)
_PAYRATE_RE = re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*([MmKk])?")
_COUNTRY_NAMES = {"JP": "Japan"}


class RobertHalfScraper(BaseScraper):
    source_id = "robert_half"
    source_name = "Robert Half Japan"
    listing_url = "https://www.roberthalf.com/jp/en/jobs"
    max_detail_requests: ClassVar[int] = 10
    max_listing_pages: ClassVar[int] = 20
    min_description_chars: ClassVar[int] = 80
    company_name: ClassVar[str] = "Robert Half Japan"

    async def scrape(self, since: datetime) -> ScrapeResult:
        """Read listing pages until every job on a page is older than ``since``."""
        jobs: list[ScrapedJob] = []
        skipped = 0
        errors: list[str] = []
        seen: set[str] = set()
        found = 0
        detail_fetches = 0

        for page in range(1, self.max_listing_pages + 1):
            page_url = self._page_url(page)
            try:
                listing_html = await self.http.get_text(page_url)
            except Exception as exc:
                if page == 1:
                    raise ScraperError(
                        f"Failed to fetch Robert Half listing {page_url}: {exc}"
                    ) from exc
                errors.append(f"listing {page_url}: {exc}")
                logger.warning(
                    "Robert Half listing page failed %s: %s", page_url, exc
                )
                break

            try:
                data = self._extract_initial_results(listing_html)
            except SourceChanged:
                if page == 1:
                    raise
                errors.append(f"listing {page_url}: initialResults JSON changed")
                logger.warning("Robert Half listing page changed: %s", page_url)
                break

            raw_jobs = [job for job in data["jobs"] if isinstance(job, dict)]
            if not raw_jobs:
                break

            page_has_recent = False
            page_new = 0
            for raw_job in raw_jobs:
                key = self._job_key(raw_job)
                if key in seen:
                    continue
                seen.add(key)
                found += 1
                page_new += 1

                posted_at = self._parse_datetime(raw_job.get("date_posted"))
                if posted_at is not None and posted_at < since:
                    skipped += 1
                    continue
                page_has_recent = True

                try:
                    job = self._parse_listing_job(raw_job)
                except ParseError as exc:
                    label = raw_job.get("job_detail_url") or key
                    errors.append(f"{label}: {exc}")
                    logger.warning("Robert Half job parse failed %s: %s", key, exc)
                    continue

                if job.posted_at is not None and job.posted_at < since:
                    skipped += 1
                    continue

                if (
                    self._needs_detail(raw_job)
                    and detail_fetches < self.max_detail_requests
                ):
                    detail_fetches += 1
                    try:
                        detail_html = await self.http.get_text(job.url)
                    except Exception as exc:
                        errors.append(f"{job.url}: {exc}")
                        logger.warning(
                            "Robert Half detail fetch failed %s: %s", job.url, exc
                        )
                    else:
                        self._enrich_from_detail(job, detail_html)

                jobs.append(job)

            # Pages are ordered newest first. If no new job on this page is in
            # the window, every later page is older too.
            if not page_has_recent or page_new == 0:
                break

        return ScrapeResult(
            source=self.source_id,
            jobs=jobs,
            found=found,
            skipped=skipped,
            errors=errors,
        )

    def _page_url(self, page: int) -> str:
        if page <= 1:
            return self.listing_url
        return f"{self.listing_url}?pagenumber={page}"

    @classmethod
    def _extract_initial_results(cls, listing_html: str) -> dict[str, Any]:
        match = _INITIAL_RESULTS_RE.search(listing_html)
        if match is None:
            raise SourceChanged(
                "Robert Half listing did not contain the initialResults JSON payload"
            )
        try:
            payload = json.loads(cls._js_string_unescape(match.group(1)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise SourceChanged(
                f"Robert Half initialResults JSON could not be parsed: {exc}"
            ) from exc

        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise SourceChanged("Robert Half initialResults JSON had no jobs list")
        return data

    @classmethod
    def _extract_job_details(cls, detail_html: str) -> dict[str, Any] | None:
        match = _JOB_DETAILS_RE.search(detail_html)
        if match is None:
            return None
        try:
            payload = json.loads(cls._js_string_unescape(match.group(1)))
        except (json.JSONDecodeError, ValueError):
            return None

        response = payload.get("jobDetailsResponse")
        if not isinstance(response, dict):
            return None
        data = response.get("data")
        if not isinstance(data, dict):
            return None
        jobs = data.get("jobs")
        if isinstance(jobs, list) and jobs and isinstance(jobs[0], dict):
            return jobs[0]
        return None

    @staticmethod
    def _js_string_unescape(raw: str) -> str:
        """Decode a JavaScript single-quoted string literal.

        The source escapes quotes as ``\\x22``/``\\x27`` and hyphens as
        ``\\u002D``. Standard escapes are handled too so the same helper works
        if the page switches encoders.
        """
        out: list[str] = []
        index = 0
        length = len(raw)
        while index < length:
            char = raw[index]
            if char != "\\":
                out.append(char)
                index += 1
                continue
            if index + 1 >= length:
                out.append("\\")
                break

            escape = raw[index + 1]
            if escape == "x" and index + 3 < length:
                out.append(chr(int(raw[index + 2 : index + 4], 16)))
                index += 4
            elif escape == "u" and index + 5 < length:
                code = int(raw[index + 2 : index + 6], 16)
                index += 6
                # Combine UTF-16 surrogate pairs emitted by some JS encoders.
                if (
                    0xD800 <= code <= 0xDBFF
                    and raw[index : index + 2] == "\\u"
                    and index + 5 < length
                ):
                    low = int(raw[index + 2 : index + 6], 16)
                    if 0xDC00 <= low <= 0xDFFF:
                        code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                        index += 6
                out.append(chr(code))
            elif escape == "/":
                out.append("/")
                index += 2
            elif escape in ("'", '"', "\\"):
                out.append(escape)
                index += 2
            elif escape == "n":
                out.append("\n")
                index += 2
            elif escape == "t":
                out.append("\t")
                index += 2
            elif escape == "r":
                out.append("\r")
                index += 2
            elif escape == "b":
                out.append("\b")
                index += 2
            elif escape == "f":
                out.append("\f")
                index += 2
            else:
                out.append(escape)
                index += 2
        return "".join(out)

    @staticmethod
    def _job_key(raw_job: dict[str, Any]) -> str:
        for field in ("unique_job_number", "sf_jo_number"):
            value = (raw_job.get(field) or "").strip()
            if value:
                return value
        url = (raw_job.get("job_detail_url") or "").strip()
        if url:
            return canonical_url(url)
        return f"{raw_job.get('jobtitle') or ''}|{raw_job.get('date_posted') or ''}"

    def _parse_listing_job(self, raw_job: dict[str, Any]) -> ScrapedJob:
        title = (raw_job.get("jobtitle") or raw_job.get("functional_role") or "").strip()
        if not title:
            raise ParseError("Missing job title")

        url = (raw_job.get("job_detail_url") or "").strip()
        if not url:
            raise ParseError(f"Missing job URL for {title}")

        description_html = self._clean_description_html(
            (raw_job.get("description") or "").strip()
        )
        summary = (raw_job.get("summary") or "").strip()
        description_text = strip_html(description_html) or summary

        posted_at_raw = raw_job.get("date_posted")
        posted_at = self._parse_datetime(posted_at_raw)
        expires_at = self._parse_datetime(raw_job.get("date_end"))

        city = (raw_job.get("city") or "").strip()
        country = (raw_job.get("country") or "").strip()
        location = self._format_location(city, country)

        remote_type = detect_remote(raw_job.get("remote"))
        employment_type = self._map_employment_type(raw_job.get("emptype"))

        salary_currency = (raw_job.get("salary_currency") or "JPY").strip() or "JPY"
        salary_min, salary_max = self._parse_salary_range(raw_job)
        salary_text = self._format_salary_text(
            salary_min,
            salary_max,
            raw_job.get("payrate_period"),
            salary_currency,
        )

        language = detect_language(title, description_text)
        location_scope = self._location_scope(
            country, location, remote_type, description_text
        )
        overseas_eligible = detect_overseas_eligible(description_text)
        classification = classify(
            title,
            description_text,
            source_is_security_category=False,
        )

        return ScrapedJob(
            source=self.source_id,
            source_job_id=(
                raw_job.get("sf_jo_number")
                or raw_job.get("unique_job_number")
                or None
            ),
            url=canonical_url(url),
            title=title,
            company=self.company_name,
            location=location,
            remote_type=remote_type,
            employment_type=employment_type,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            salary_text=salary_text,
            description_text=description_text or None,
            description_html=description_html or None,
            posted_at=posted_at,
            posted_at_raw=posted_at_raw,
            expires_at=expires_at,
            language=language,
            location_scope=location_scope,
            overseas_eligible=overseas_eligible,
            security_tags=classification.tags,
            role_category=classification.role_category,
            raw=self._raw_summary(raw_job),
        )

    @staticmethod
    def _clean_description_html(description_html: str) -> str:
        """Drop tracking pixels and active content from source HTML."""
        if not description_html:
            return ""
        # html.parser keeps the fragment as-is instead of adding html/body tags.
        soup = BeautifulSoup(description_html, "html.parser")
        for tag in soup.find_all(["img", "script", "iframe", "object", "embed"]):
            tag.decompose()
        return str(soup)

    def _needs_detail(self, raw_job: dict[str, Any]) -> bool:
        description = strip_html(raw_job.get("description") or "")
        summary = (raw_job.get("summary") or "").strip()
        return max(len(description), len(summary)) < self.min_description_chars

    def _enrich_from_detail(self, job: ScrapedJob, detail_html: str) -> None:
        detail_job = self._extract_job_details(detail_html)
        description_html = ""
        if detail_job is not None:
            description_html = self._clean_description_html(
                (detail_job.get("description") or "").strip()
            )
            summary = (detail_job.get("summary") or "").strip()
            if description_html:
                job.description_html = description_html
                job.description_text = strip_html(description_html) or summary

        if not description_html:
            jsonld = extract_job_posting_jsonld(detail_html)
            if jsonld is not None:
                description_html = self._clean_description_html(
                    (jsonld.get("description") or "").strip()
                )
                if description_html:
                    job.description_html = description_html
                    job.description_text = strip_html(description_html)

        if job.description_text:
            job.language = detect_language(job.title, job.description_text)
            job.overseas_eligible = detect_overseas_eligible(job.description_text)
            classification = classify(
                job.title,
                job.description_text,
                source_is_security_category=False,
            )
            job.security_tags = classification.tags
            job.role_category = classification.role_category

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        parsed = parse_iso_datetime(str(value))
        return to_utc(parsed) if parsed is not None else None

    @staticmethod
    def _format_location(city: str, country: str) -> str | None:
        city = city.strip()
        country = country.strip()
        country_label = _COUNTRY_NAMES.get(country.upper(), country)
        if city and country_label:
            if country_label.lower() in city.lower():
                return city
            return f"{city}, {country_label}"
        return city or country_label or None

    @staticmethod
    def _location_scope(
        country: str,
        location: str | None,
        remote_type: str | None,
        description: str | None,
    ) -> str:
        if country and country.upper() != "JP":
            # The model has no international-onsite scope; only mark remote
            # non-Japan roles explicitly and leave the rest unknown/hidden.
            return "international_remote" if remote_type == "remote" else "unknown"
        return detect_location_scope(location, remote_type, description)

    @staticmethod
    def _map_employment_type(value: Any) -> str:
        text = str(value or "").strip().lower()
        mapping = {
            "perm": "full_time",
            "permanent": "full_time",
            "full time": "full_time",
            "temp": "contract",
            "temporary": "contract",
            "contract": "contract",
            "part time": "part_time",
            "part-time": "part_time",
            "intern": "internship",
            "internship": "internship",
        }
        if text in mapping:
            return mapping[text]
        return detect_employment_type(text)

    @classmethod
    def _parse_salary_range(
        cls, raw_job: dict[str, Any]
    ) -> tuple[int | None, int | None]:
        salary_min = cls._parse_payrate(raw_job.get("payrate_min"))
        salary_max = cls._parse_payrate(raw_job.get("payrate_max"))
        if salary_min is None and salary_max is None:
            period = str(raw_job.get("payrate_period") or "").strip().lower()
            if period == "yearly":
                yearly = cls._parse_payrate(raw_job.get("payrate_yearly"))
                if yearly is not None:
                    salary_min = salary_max = yearly
        return salary_min, salary_max

    @staticmethod
    def _parse_payrate(value: Any) -> int | None:
        if value is None:
            return None
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        match = _PAYRATE_RE.search(text)
        if match is None:
            return None
        try:
            amount = float(match.group(1))
        except ValueError:
            return None
        suffix = (match.group(2) or "").lower()
        multiplier = {"m": 1_000_000, "k": 1_000}.get(suffix, 1)
        return int(amount * multiplier)

    @staticmethod
    def _format_salary_text(
        salary_min: int | None,
        salary_max: int | None,
        period: Any,
        currency: str,
    ) -> str | None:
        if salary_min is None and salary_max is None:
            return None
        symbol = {"JPY": "¥", "USD": "$", "EUR": "€"}.get(currency, f"{currency} ")
        suffix = {
            "yearly": " per year",
            "monthly": " per month",
            "hourly": " per hour",
        }.get(str(period or "").strip().lower(), "")
        if salary_min is not None and salary_max is not None:
            if salary_min == salary_max:
                return f"{symbol}{salary_min:,}{suffix}"
            return f"{symbol}{salary_min:,} - {symbol}{salary_max:,}{suffix}"
        if salary_min is not None:
            return f"{symbol}{salary_min:,}+{suffix}"
        return f"Up to {symbol}{salary_max:,}{suffix}"

    @staticmethod
    def _raw_summary(raw_job: dict[str, Any]) -> dict[str, Any]:
        fields = (
            "sf_jo_number",
            "unique_job_number",
            "jobtitle",
            "functional_role",
            "date_posted",
            "date_end",
            "city",
            "country",
            "remote",
            "emptype",
            "payrate_min",
            "payrate_max",
            "payrate_yearly",
            "payrate_period",
            "salary_currency",
            "industry",
            "lob_code",
            "branch",
            "language_key",
            "summary",
        )
        return {
            field: raw_job[field]
            for field in fields
            if raw_job.get(field) not in (None, "")
        }
