from datetime import datetime

from app.scrapers.base import BaseScraper, ScraperError, ScrapeResult


class TokyoDevScraper(BaseScraper):
    source_id = "tokyo_dev"
    source_name = "TokyoDev"
    listing_url = "https://www.tokyodev.com/jobs/security"
    is_security_category = True

    async def scrape(self, since: datetime) -> ScrapeResult:
        raise ScraperError(
            "TokyoDev scraper is not implemented yet (planned for Phase 3)."
        )
