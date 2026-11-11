from datetime import datetime

from app.scrapers.base import BaseScraper, ScraperError, ScrapeResult


class JapanDevScraper(BaseScraper):
    source_id = "japan_dev"
    source_name = "JapanDev"
    listing_url = "https://japan-dev.com/security-jobs-in-japan"
    is_security_category = True

    async def scrape(self, since: datetime) -> ScrapeResult:
        raise ScraperError(
            "JapanDev scraper is not implemented yet (planned for Phase 3)."
        )
