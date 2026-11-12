import logging
import re
from datetime import datetime
from typing import ClassVar
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

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
from app.services.dates import parse_date_only, parse_iso_datetime, to_utc
from app.services.jsonld import extract_job_posting_jsonld
from app.services.normalize import (
    canonical_url,
    detect_employment_type,
    detect_language,
    detect_location_scope,
    detect_overseas_eligible,
    detect_remote,
    normalize_width,
    parse_salary,
    strip_html,
)

logger = logging.getLogger(__name__)

# Daijob detail links: /en/jobs/detail/<id>
_DETAIL_PATH_RE = re.compile(r"^/en/jobs/detail/(\d+)/?$")
_UPDATED_RE = re.compile(r"\bUpdated\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
_ACTIVATED_RE = re.compile(r"\bActivated\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
_CONFIDENTIAL_RE = re.compile(
    r"(not publicly visible|confidential|非公開|公開していません)", re.IGNORECASE
)
_SEARCH_BASE = "https://www.daijob.com/en/jobs/search"


class DaijobScraper(BaseScraper):
    source_id = "daijob"
    source_name = "Daijob"
    listing_url = "https://www.daijob.com/en/jobs/search?js_jt%5B%5D=503&fl=1&pg=0"
    max_detail_requests: ClassVar[int] = 40
    is_security_category = True

    # The category is the primary source; two curated Japanese keywords catch
    # security roles filed under other job types. Keyword pages are broad, so
    # only their first page is read and detail fetches stay capped.
    keyword_searches: ClassVar[tuple[str, ...]] = (
        "サイバーセキュリティ",
        "情報セキュリティ",
    )
    category_pages: ClassVar[int] = 2
    keyword_pages: ClassVar[int] = 1

    async def scrape(self, since: datetime) -> ScrapeResult:
        errors: list[str] = []
        detail_urls = await self._collect_detail_urls(errors)
        if not detail_urls:
            raise SourceChanged("Daijob listing yielded no job detail links")

        found = len(detail_urls)

        jobs: list[ScrapedJob] = []
        skipped = 0

        for detail_url in detail_urls[: self.max_detail_requests]:
            try:
                detail_html = await self.http.get_text(detail_url)
            except Exception as exc:
                errors.append(f"{detail_url}: {exc}")
                logger.warning("Daijob detail fetch failed %s: %s", detail_url, exc)
                continue
            try:
                job = self._parse_detail(detail_html, detail_url)
            except ParseError as exc:
                errors.append(f"{detail_url}: {exc}")
                logger.warning("Daijob detail parse failed %s: %s", detail_url, exc)
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

    async def _collect_detail_urls(self, errors: list[str]) -> list[str]:
        plans = [(self.listing_url, self.category_pages)]
        plans.extend(
            (self._keyword_url(keyword), self.keyword_pages)
            for keyword in self.keyword_searches
        )

        seen: dict[str, str] = {}
        for index, (search_url, max_pages) in enumerate(plans):
            try:
                listing_html = await self.http.get_text(search_url)
            except Exception as exc:
                # A broken primary category is a source-wide failure. A broken
                # optional keyword search is recorded but does not abort the run.
                if index == 0:
                    raise ScraperError(
                        f"Failed to fetch Daijob listing {search_url}: {exc}"
                    ) from exc
                errors.append(f"listing {search_url}: {exc}")
                logger.warning("Daijob keyword search failed %s: %s", search_url, exc)
                continue

            pages = [listing_html]
            for page_url in self._pager_urls(listing_html, search_url, max_pages):
                try:
                    pages.append(await self.http.get_text(page_url))
                except Exception as exc:
                    errors.append(f"listing {page_url}: {exc}")
                    logger.warning(
                        "Daijob listing page failed %s: %s", page_url, exc
                    )

            for page_html in pages:
                for job_id, detail_url in self._extract_detail_urls(
                    page_html, search_url
                ).items():
                    seen.setdefault(job_id, detail_url)

        return list(seen.values())

    @staticmethod
    def _keyword_url(keyword: str) -> str:
        query = urlencode({"kw": keyword, "fl": "1", "pg": "0"})
        return f"{_SEARCH_BASE}?{query}"

    @staticmethod
    def _pager_urls(
        listing_html: str, base_url: str, max_pages: int
    ) -> list[str]:
        if max_pages <= 1:
            return []

        soup = BeautifulSoup(listing_html, "lxml")
        pages: dict[int, str] = {}
        for anchor in soup.select("nav.pager a[href]"):
            query = parse_qs(urlsplit(anchor["href"]).query)
            values = query.get("page")
            if not values:
                continue
            try:
                page = int(values[0])
            except (TypeError, ValueError):
                continue
            if page <= 1:
                continue
            pages.setdefault(page, urljoin(base_url, anchor["href"]))
        ordered = [pages[page] for page in sorted(pages)]
        return ordered[: max_pages - 1]

    @staticmethod
    def _extract_detail_urls(listing_html: str, base_url: str) -> dict[str, str]:
        soup = BeautifulSoup(listing_html, "lxml")
        seen: dict[str, str] = {}
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            path = urlsplit(href).path
            match = _DETAIL_PATH_RE.match(path)
            if not match:
                continue
            seen.setdefault(match.group(1), canonical_url(urljoin(base_url, href)))
        return seen

    def _parse_detail(self, detail_html: str, detail_url: str) -> ScrapedJob | None:
        soup = BeautifulSoup(detail_html, "lxml")
        jsonld = extract_job_posting_jsonld(detail_html) or {}
        meta = self._parse_meta_rows(soup)
        sections = self._parse_sections(soup)

        title = self._extract_title(jsonld, soup)
        if not title:
            raise ParseError(f"Missing job title on {detail_url}")

        description_html = (jsonld.get("description") or "").strip()
        if not description_html:
            description_html = self._section_body_html(soup, "Job Description")
        description_text = strip_html(description_html)

        header_text = self._date_header_text(soup)
        posted_at_raw = self._extract_date(header_text, _ACTIVATED_RE)
        if not posted_at_raw:
            posted_at_raw = jsonld.get("datePosted")
        posted_at = (
            to_utc(parse_date_only(posted_at_raw)) if posted_at_raw else None
        )

        updated_raw = self._extract_date(header_text, _UPDATED_RE)
        source_updated_at = (
            to_utc(parse_date_only(updated_raw)) if updated_raw else None
        )

        expires_raw = jsonld.get("validThrough")
        expires_at = (
            to_utc(parse_iso_datetime(expires_raw)) if expires_raw else None
        )

        company = self._resolve_company(meta, jsonld, soup)
        location = self._parse_location(soup) or self._location_from_jsonld(jsonld)

        job_type = meta.get("Job Type", "")
        industry = meta.get("Industry", "")

        salary_text = sections.get("Salary")
        salary = parse_salary(salary_text)
        salary_min, salary_max = self._salary_bounds(salary, salary_text)
        salary_currency = salary.currency
        if salary_min is None and salary_max is None:
            salary_min, salary_max, salary_currency = self._salary_from_jsonld(jsonld)

        employment_type = detect_employment_type(
            " ".join(
                [
                    job_type,
                    sections.get("Job Contract Period", ""),
                    title,
                    description_text[:2000],
                ]
            )
        )

        remote_signal = " ".join(
            [
                title,
                description_text,
                sections.get("Working Hours", ""),
                header_text,
            ]
        )
        remote_type = detect_remote(remote_signal)
        if remote_type == "unknown":
            remote_type = self._remote_from_jsonld(jsonld)

        language = detect_language(title, description_text)
        location_scope = detect_location_scope(location, remote_type, description_text)
        overseas_eligible = detect_overseas_eligible(
            " ".join(
                [
                    title,
                    description_text,
                    sections.get("Job Requirements", ""),
                ]
            )
        )

        japanese_level = self._detect_japanese_level(
            sections.get("Japanese Level") or ""
        )

        classification = classify(
            title,
            description_text,
            source_tags=[],
            source_is_security_category=self.is_security_category,
        )

        return ScrapedJob(
            source=self.source_id,
            source_job_id=self._extract_source_job_id(jsonld, detail_url),
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
            source_updated_at=source_updated_at,
            expires_at=expires_at,
            japanese_level=japanese_level,
            language=language,
            location_scope=location_scope,
            overseas_eligible=overseas_eligible,
            security_tags=classification.tags,
            role_category=classification.role_category,
            raw={
                "jsonld": jsonld or None,
                "meta": meta,
                "job_type": job_type,
                "industry": industry,
            },
        )

    @staticmethod
    def _extract_title(jsonld: dict, soup: BeautifulSoup) -> str:
        title = (jsonld.get("title") or "").strip()
        if not title:
            element = soup.select_one(".job-detail__title")
            if element:
                title = element.get_text(" ", strip=True)
        return re.sub(r"\s+", " ", title).strip()

    @staticmethod
    def _date_header_text(soup: BeautifulSoup) -> str:
        element = soup.select_one(".text-end.text-secondary.fs-12px")
        if element:
            return element.get_text(" ", strip=True)
        article = soup.select_one("article.job-detail")
        if article:
            return article.get_text(" ", strip=True)
        return soup.get_text(" ", strip=True)

    @staticmethod
    def _extract_date(text: str, pattern: re.Pattern[str]) -> str | None:
        match = pattern.search(text or "")
        return match.group(1) if match else None

    @staticmethod
    def _parse_meta_rows(soup: BeautifulSoup) -> dict[str, str]:
        rows: dict[str, str] = {}
        for row in soup.select(".job-detail__meta-row"):
            dt = row.select_one("dt")
            dd = row.select_one("dd")
            if not dt or not dd:
                continue
            label = dt.get_text(" ", strip=True).rstrip(":").strip()
            value = re.sub(r"\s+", " ", dd.get_text(" ", strip=True)).strip()
            if label and label not in rows:
                rows[label] = value
        return rows

    @staticmethod
    def _parse_sections(soup: BeautifulSoup) -> dict[str, str]:
        sections: dict[str, str] = {}
        for section in soup.select("section.job-section"):
            label_el = section.select_one(".job-section__label")
            body = section.select_one(".job-section__body")
            if not label_el or not body:
                continue
            label = label_el.get_text(" ", strip=True)
            if label and label not in sections:
                sections[label] = re.sub(
                    r"\s+", " ", body.get_text(" ", strip=True)
                ).strip()
        return sections

    @staticmethod
    def _section_body_html(soup: BeautifulSoup, label: str) -> str:
        for section in soup.select("section.job-section"):
            label_el = section.select_one(".job-section__label")
            if not label_el or label_el.get_text(" ", strip=True) != label:
                continue
            body = section.select_one(".job-section__body")
            if body:
                return str(body)
        return ""

    @staticmethod
    def _parse_location(soup: BeautifulSoup) -> str | None:
        for row in soup.select(".job-detail__meta-row"):
            dt = row.select_one("dt")
            if not dt:
                continue
            if not dt.get_text(" ", strip=True).startswith("Location"):
                continue
            dd = row.select_one("dd")
            if not dd:
                return None

            parts: list[str] = []
            anchors: list[str] = []
            for anchor in dd.find_all("a"):
                text = anchor.get_text(" ", strip=True)
                if not text:
                    continue
                anchors.append(text)
                if text in {"Asia", "Japan"}:
                    continue
                if text not in parts:
                    parts.append(text)
            if parts:
                return ", ".join(parts)
            if "Japan" in anchors:
                return "Japan"
            joined = " ".join(anchors)
            return joined or None
        return None

    @staticmethod
    def _location_from_jsonld(jsonld: dict) -> str | None:
        locations = jsonld.get("jobLocation") or []
        if isinstance(locations, dict):
            locations = [locations]
        parts: list[str] = []
        for location in locations:
            if not isinstance(location, dict):
                continue
            address = location.get("address") or {}
            if not isinstance(address, dict):
                continue
            locality = (address.get("addressLocality") or "").strip()
            region = (address.get("addressRegion") or "").strip()
            value = ", ".join(part for part in (locality, region) if part)
            if value and value not in parts:
                parts.append(value)
        return ", ".join(parts) or None

    @staticmethod
    def _resolve_company(
        meta: dict[str, str], jsonld: dict, soup: BeautifulSoup
    ) -> str:
        company = meta.get("Company Name", "").strip()
        if company and not _CONFIDENTIAL_RE.search(company):
            return company

        hiring_org = jsonld.get("hiringOrganization") or {}
        name = (hiring_org.get("name") or "").strip()
        if name and not _CONFIDENTIAL_RE.search(name):
            return name

        managed_by = meta.get("This posting is managed by", "").strip()
        if managed_by:
            return managed_by

        visible = soup.select_one(".job-detail__company")
        if visible:
            text = re.sub(r"\s+", " ", visible.get_text(" ", strip=True)).strip()
            if text:
                return text
        return "Daijob"

    @staticmethod
    def _salary_bounds(salary, salary_text: str | None) -> tuple[int | None, int | None]:
        if salary.min is None and salary.max is None:
            return None, None
        text = salary_text or ""
        lowered = normalize_width(text).lower()
        if salary.min == salary.max:
            if "over" in lowered or "以上" in text:
                return salary.min, None
            if "under" in lowered or "以下" in text:
                return None, salary.max
        return salary.min, salary.max

    @staticmethod
    def _salary_from_jsonld(
        jsonld: dict,
    ) -> tuple[int | None, int | None, str]:
        base_salary = jsonld.get("baseSalary") or {}
        if not isinstance(base_salary, dict):
            return None, None, "JPY"
        value = base_salary.get("value") or {}
        if not isinstance(value, dict):
            return None, None, "JPY"
        return (
            DaijobScraper._parse_int(value.get("minValue")),
            DaijobScraper._parse_int(value.get("maxValue")),
            base_salary.get("currency") or "JPY",
        )

    @staticmethod
    def _detect_japanese_level(text: str) -> str | None:
        if not text:
            return None
        normalized = normalize_width(text)
        lowered = normalized.lower()
        if "native" in lowered or "ネイティブ" in normalized:
            return "native"
        if "fluent" in lowered or "流暢" in normalized or "N1" in normalized:
            return "fluent"
        if "business" in lowered or "ビジネス" in normalized or "N2" in normalized:
            return "business"
        if (
            "conversational" in lowered
            or "daily conversation" in lowered
            or "会話" in normalized
        ):
            return "conversational"
        if "basic" in lowered or "初級" in normalized:
            return "basic"
        if (
            "none" in lowered
            or "not required" in lowered
            or "no japanese required" in lowered
            or "japanese not required" in lowered
            or "不要" in normalized
        ):
            return "none"
        return None

    @staticmethod
    def _remote_from_jsonld(jsonld: dict) -> str:
        job_location_type = str(jsonld.get("jobLocationType") or "").upper()
        if job_location_type == "TELECOMMUTE":
            return "remote"
        return "unknown"

    @staticmethod
    def _extract_source_job_id(jsonld: dict, detail_url: str) -> str | None:
        identifier = jsonld.get("identifier")
        if isinstance(identifier, dict):
            value = identifier.get("value")
            if value:
                return str(value)
        elif identifier:
            return str(identifier)
        path = urlsplit(detail_url).path.rstrip("/")
        return path.rsplit("/", 1)[-1] or None

    @staticmethod
    def _parse_int(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value).replace(",", ""))
        except (ValueError, TypeError):
            return None
