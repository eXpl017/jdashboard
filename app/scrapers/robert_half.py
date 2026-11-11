from datetime import datetime

from app.scrapers.base import BaseScraper, ScraperError, ScrapeResult


class RobertHalfScraper(BaseScraper):
    source_id = "robert_half"
    source_name = "Robert Half Japan"
    listing_url = "https://www.roberthalf.com/jp/en/jobs"

    async def scrape(self, since: datetime) -> ScrapeResult:
        raise ScraperError(
            "Robert Half scraper is not implemented yet (planned for Phase 3)."
        )
