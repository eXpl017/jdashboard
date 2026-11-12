from typing import TYPE_CHECKING

from app.config import Settings
from app.scrapers.base import BaseScraper
from app.scrapers.daijob import DaijobScraper
from app.scrapers.japan_dev import JapanDevScraper
from app.scrapers.michael_page import MichaelPageScraper
from app.scrapers.robert_half import RobertHalfScraper
from app.scrapers.tokyo_dev import TokyoDevScraper

if TYPE_CHECKING:
    from app.services.http import HttpClient

SCRAPER_CLASSES: dict[str, type[BaseScraper]] = {
    "michael_page": MichaelPageScraper,
    "japan_dev": JapanDevScraper,
    "tokyo_dev": TokyoDevScraper,
    "daijob": DaijobScraper,
    "robert_half": RobertHalfScraper,
}

SOURCE_NAMES: dict[str, str] = {
    source_id: scraper_cls.source_name for source_id, scraper_cls in SCRAPER_CLASSES.items()
}


def _is_enabled(source_id: str, config: Settings) -> bool:
    return bool(getattr(config, f"enable_{source_id}", True))


def enabled_source_ids(config: Settings) -> list[str]:
    return [source_id for source_id in SCRAPER_CLASSES if _is_enabled(source_id, config)]


def build_registry(http: "HttpClient", config: Settings) -> dict[str, BaseScraper]:
    """Instantiate enabled scrapers, keyed by source ID."""
    return {
        source_id: SCRAPER_CLASSES[source_id](http, config)
        for source_id in enabled_source_ids(config)
    }
