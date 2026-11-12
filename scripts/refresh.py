"""Run a manual refresh from the command line.

Uses the same refresh service and scrapers as the dashboard UI, so the result is
identical to a UI-triggered refresh. Explicitly user-initiated only.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from app.config import settings
from app.db import SessionLocal
from app.logging_config import configure_logging
from app.scrapers.base import BaseScraper
from app.scrapers.registry import build_registry
from app.services.http import HttpClient
from app.services.refresh import RefreshService


def build_scrapers(source_id: str | None) -> dict[str, BaseScraper]:
    """Return the full registry, or a single-source registry when requested."""
    registry = build_registry(HttpClient(settings), settings)
    if source_id is None:
        return registry
    if source_id not in registry:
        raise SystemExit(f"Unknown source: {source_id}")
    return {source_id: registry[source_id]}


async def run_refresh(window_days: int, source_id: str | None) -> dict[str, object]:
    """Start and await a refresh; return a JSON-serializable summary."""
    service = RefreshService(
        session_factory=SessionLocal,
        scrapers=build_scrapers(source_id),
        default_window_days=window_days,
    )
    progress = await service.start(window_days=window_days)
    await service.wait()
    final = service.snapshot()
    status = final.status if final is not None else "failed"
    sources: dict[str, dict[str, object]] = {}
    if final is not None:
        sources = {
            source_id: {
                "status": source.status,
                "found": source.found,
                "new": source.new,
                "updated": source.updated,
                "skipped": source.skipped,
                "errors": source.errors,
                "error_message": source.error_message,
            }
            for source_id, source in final.sources.items()
        }
    return {
        "run_id": progress.run_id,
        "status": status,
        "window_days": window_days,
        "sources": sources,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a manual dashboard refresh.")
    parser.add_argument("--window-days", type=int, default=settings.default_window_days)
    parser.add_argument("--source", type=str, default=None, help="Refresh a single source")
    args = parser.parse_args(argv)

    if args.window_days < 1 or args.window_days > 30:
        parser.error("--window-days must be between 1 and 30")

    configure_logging()

    async def _execute() -> dict[str, object]:
        return await run_refresh(args.window_days, args.source)

    result = asyncio.run(_execute())
    print(json.dumps(result, default=str, ensure_ascii=False))
    final_status = str(result.get("status") or "failed")
    return 0 if final_status != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
