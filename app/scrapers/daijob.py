from datetime import datetime

from app.scrapers.base import BaseScraper, ScraperError, ScrapeResult


class DaijobScraper(BaseScraper):
    source_id = "daijob"
    source_name = "Daijob"
    listing_url = "https://www.daijob.com/en/jobs/search?js_jt%5B%5D=503&fl=1&pg=0"
    is_security_category = True

    async def scrape(self, since: datetime) -> ScrapeResult:
        raise ScraperError(
            "Daijob scraper is not implemented yet (planned for Phase 3)."
        )
