import logging
import re
from datetime import datetime
from typing import ClassVar
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ParseError, ScrapedJob, ScraperError, ScrapeResult
from app.services.classify import classify
from app.services.dates import parse_date_only, parse_iso_datetime, to_utc
from app.services.jsonld import extract_job_posting_jsonld
from app.services.normalize import (
    canonical_url,
    detect_employment_type,
    detect_language,
    detect_location_scope,
    detect_remote,
    strip_html,
)

logger = logging.getLogger(__name__)

# TokyoDev detail links: /companies/<company>/jobs/<slug>
_JOB_PATH_RE = re.compile(r"^/companies/[^/]+/jobs/[^/?#]+/?$")
_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
_VERIFIED_RE = re.compile(r"Verified as active\s+(.+?)\s*$", re.I)


class TokyoDevScraper(BaseScraper):
    source_id = "tokyo_dev"
    source_name = "TokyoDev"
    listing_url = "https://www.tokyodev.com/jobs/security"
    atom_url: ClassVar[str] = "https://www.tokyodev.com/jobs/atom.xml"
    max_detail_requests: ClassVar[int] = 40
    is_security_category = True

    async def scrape(self, since: datetime) -> ScrapeResult:
        try:
            listing_html = await self.http.get_text(self.listing_url)
        except Exception as exc:
            raise ScraperError(
                f"Failed to fetch TokyoDev listing {self.listing_url}: {exc}"
            ) from exc

        detail_urls = self._extract_detail_urls(listing_html, self.listing_url)
        if not detail_urls:
            # The category page is the primary source; the Atom feed is a
            # discovery-only fallback when the page yields no job links.
            logger.warning("TokyoDev listing had no job links; trying Atom fallback")
            try:
                atom_xml = await self.http.get_text(self.atom_url)
            except Exception as exc:
                raise ScraperError(
                    f"Failed to fetch TokyoDev Atom feed {self.atom_url}: {exc}"
                ) from exc
            detail_urls = self._extract_atom_urls(atom_xml, self.atom_url, since)

        found = len(detail_urls)

        jobs: list[ScrapedJob] = []
        skipped = 0
        errors: list[str] = []

        for detail_url in detail_urls[: self.max_detail_requests]:
            try:
                detail_html = await self.http.get_text(detail_url)
            except Exception as exc:
                errors.append(f"{detail_url}: {exc}")
                logger.warning("TokyoDev detail fetch failed %s: %s", detail_url, exc)
                continue
            try:
                job = self._parse_detail(detail_html, detail_url)
            except ParseError as exc:
                errors.append(f"{detail_url}: {exc}")
                logger.warning("TokyoDev detail parse failed %s: %s", detail_url, exc)
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
            path = urlsplit(href).path
            if not _JOB_PATH_RE.match(path):
                continue
            absolute = canonical_url(urljoin(base_url, href))
            seen.setdefault(path.rstrip("/"), absolute)
        return list(seen.values())

    @staticmethod
    def _extract_atom_urls(
        atom_xml: str, base_url: str, since: datetime | None = None
    ) -> list[str]:
        try:
            root = ElementTree.fromstring(atom_xml)
        except ElementTree.ParseError as exc:
            raise ParseError(f"Invalid Atom feed: {exc}") from exc

        seen: dict[str, str] = {}
        for entry in root.findall("a:entry", _ATOM_NS):
            if since is not None:
                updated_raw = entry.findtext("a:updated", namespaces=_ATOM_NS) or (
                    entry.findtext("a:published", namespaces=_ATOM_NS)
                )
                updated = parse_iso_datetime(updated_raw)
                if updated is not None and to_utc(updated) < since:
                    continue
            for link in entry.findall("a:link", _ATOM_NS):
                if link.get("rel", "alternate") != "alternate":
                    continue
                href = link.get("href")
                if not href:
                    continue
                path = urlsplit(href).path
                if not _JOB_PATH_RE.match(path):
                    continue
                absolute = canonical_url(urljoin(base_url, href))
                seen.setdefault(path.rstrip("/"), absolute)
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
        posted_at = to_utc(parse_iso_datetime(posted_at_raw)) if posted_at_raw else None

        hiring_org = jsonld.get("hiringOrganization") or {}
        company = (hiring_org.get("name") or "TokyoDev").strip() or "TokyoDev"

        employment_type = detect_employment_type(jsonld.get("employmentType") or "")

        location = self._format_location((jsonld.get("jobLocation") or {}).get("address"))

        base_salary = jsonld.get("baseSalary") or {}
        salary_value = base_salary.get("value") or {}
        salary_min = self._parse_int(salary_value.get("minValue"))
        salary_max = self._parse_int(salary_value.get("maxValue"))
        salary_currency = base_salary.get("currency") or "JPY"
        salary_text = None
        if salary_min is not None and salary_max is not None:
            salary_text = f"¥{salary_min:,} - ¥{salary_max:,} per year"

        html_fields = self._parse_detail_html(detail_html)
        remote_type = html_fields["remote_type"] or self._remote_from_jsonld(jsonld)

        source_job_id = self._extract_source_job_id(jsonld, detail_url)

        language = detect_language(title, description_text)
        location_scope = detect_location_scope(location, remote_type, description_text)
        overseas_eligible = html_fields["overseas_eligible"]

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
            source_updated_at=html_fields["source_updated_at"],
            japanese_level=html_fields["japanese_level"],
            language=language,
            location_scope=location_scope,
            overseas_eligible=overseas_eligible,
            security_tags=classification.tags,
            role_category=classification.role_category,
            raw={"jsonld": jsonld},
        )

    @staticmethod
    def _format_location(address: dict | None) -> str | None:
        if not address:
            return None
        locality = (address.get("addressLocality") or "").strip()
        region = (address.get("addressRegion") or "").strip()
        if locality and region and region.lower() not in locality.lower():
            return f"{locality}, {region}"
        return locality or region or None

    @staticmethod
    def _parse_detail_html(detail_html: str) -> dict[str, object]:
        soup = BeautifulSoup(detail_html, "lxml")
        header = soup.select_one("section#job-header") or soup
        header_text = header.get_text(" ", strip=True)

        overseas_eligible: bool | None = None
        lowered = header_text.lower()
        if "apply from abroad" in lowered:
            overseas_eligible = True
        elif "japan residents only" in lowered:
            overseas_eligible = False

        verified_at: datetime | None = None
        for el in header.select("[data-tooltip-content-value]"):
            match = _VERIFIED_RE.search(el.get("data-tooltip-content-value") or "")
            if match:
                parsed = parse_date_only(match.group(1))
                if parsed is not None:
                    verified_at = to_utc(parsed)
                break

        return {
            "remote_type": detect_remote(header_text),
            "overseas_eligible": overseas_eligible,
            "japanese_level": TokyoDevScraper._detect_japanese_level(header_text),
            "source_updated_at": verified_at,
        }

    @staticmethod
    def _detect_japanese_level(text: str) -> str | None:
        lowered = text.lower()
        if "no japanese required" in lowered:
            return "none"
        if "fluent japanese" in lowered:
            return "fluent"
        if "business japanese" in lowered:
            return "business"
        if "conversational japanese" in lowered:
            return "conversational"
        if "basic japanese" in lowered:
            return "basic"
        return None

    @staticmethod
    def _remote_from_jsonld(jsonld: dict) -> str:
        job_location_type = (jsonld.get("jobLocationType") or "").upper()
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
