import html as html_module
import json
from collections.abc import Iterator
from typing import Any

from bs4 import BeautifulSoup


def _iter_objects(data: Any) -> Iterator[dict[str, Any]]:
    if isinstance(data, dict):
        yield data
        graph = data.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _iter_objects(item)
    elif isinstance(data, list):
        for item in data:
            yield from _iter_objects(item)


def _is_job_posting(obj: dict[str, Any]) -> bool:
    obj_type = obj.get("@type")
    types = obj_type if isinstance(obj_type, list) else [obj_type]
    for value in types:
        if isinstance(value, str) and value.rstrip("/").endswith("JobPosting"):
            return True
    return False


def extract_job_posting_jsonld(html: str) -> dict[str, Any] | None:
    """Return the first schema.org JobPosting from ``<script type=application/ld+json>``."""
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw or not raw.strip():
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:
                data = json.loads(html_module.unescape(raw))
            except json.JSONDecodeError:
                continue

        for obj in _iter_objects(data):
            if _is_job_posting(obj):
                return obj
    return None
