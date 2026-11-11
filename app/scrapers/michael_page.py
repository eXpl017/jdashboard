from datetime import datetime

from app.scrapers.base import BaseScraper, ScraperError, ScrapeResult


class MichaelPageScraper(BaseScraper):
    source_id = "michael_page"
    source_name = "Michael Page Japan"
    listing_url = "https://www.michaelpage.co.jp/en/jobs/it-security"
    is_security_category = True

    async def scrape(self, since: datetime) -> ScrapeResult:
        raise ScraperError(
            "Michael Page scraper is not implemented yet (planned for Phase 3)."
        )
