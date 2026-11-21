from __future__ import annotations

from urllib.parse import urlparse

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui


def _wait_ready(page: Page) -> None:
    page.goto("/")
    expect(page.locator(".job-card")).not_to_have_count(0)


def test_no_console_errors_and_no_external_requests(page: Page, base_url: str) -> None:
    console_errors: list[str] = []
    page_errors: list[str] = []
    external_requests: list[str] = []

    def on_console(msg) -> None:
        if msg.type == "error":
            console_errors.append(msg.text)

    def on_page_error(exc) -> None:
        page_errors.append(str(exc))

    def on_request(request) -> None:
        parsed = urlparse(request.url)
        host = parsed.hostname or ""
        if host and host not in {"127.0.0.1", "localhost", "::1"}:
            external_requests.append(request.url)

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("request", on_request)

    # Guard: never trigger a real refresh against live job sites.
    def handle_refresh(route) -> None:
        if route.request.method == "POST":
            route.fulfill(status=501, body="blocked in ui tests")
        else:
            route.fallback()

    page.route("**/api/refresh", handle_refresh)
    page.route("**/api/refresh/**", handle_refresh)

    _wait_ready(page)
    # Let any late async work settle.
    page.wait_for_timeout(300)

    assert console_errors == []
    assert page_errors == []
    assert external_requests == []


def test_accessibility_labels_live_regions_and_keyboard_details(page: Page, base_url: str) -> None:
    _wait_ready(page)

    # Labeled controls
    label_for_ids = [
        "filter-q",
        "filter-source",
        "filter-role",
        "filter-language",
        "filter-location",
        "filter-location-scope",
        "filter-remote",
        "filter-visa",
        "filter-tag",
        "filter-days",
        "filter-sort",
        "filter-include-active",
    ]
    for control_id in label_for_ids:
        has_label = page.evaluate(
            """
            (id) => {
              const el = document.getElementById(id);
              if (!el) return false;
              if (el.labels && el.labels.length > 0) return true;
              const label = document.querySelector(`label[for="${id}"]`);
              return !!label;
            }
            """,
            control_id,
        )
        assert has_label, f"missing label for {control_id}"

    # ARIA live regions / busy state
    expect(page.locator("#job-list")).to_have_attribute("aria-live", "polite")
    expect(page.locator("#refresh-status-line")).to_have_attribute("aria-live", "polite")
    expect(page.locator("#job-list")).to_have_attribute("aria-busy", "false")

    # Keyboard-toggleable Details
    first_card = page.locator(".job-card").first
    summary = first_card.locator("summary")
    details = first_card.locator("details.job-card__details")
    expect(details).not_to_have_attribute("open", "")
    summary.focus()
    page.keyboard.press("Enter")
    expect(details).to_have_attribute("open", "")
    expect(first_card.locator(".job-card__description")).to_be_visible()


def test_empty_state_message_when_filters_match_nothing(page: Page, base_url: str) -> None:
    _wait_ready(page)
    page.locator("#filter-q").fill("zzzz-no-such-job-zzzz")
    expect(page.locator(".job-list__state--empty, .job-list__state")).to_be_visible()
    expect(page.locator("#job-list")).to_contain_text("No jobs found")
    expect(page.locator(".job-card")).to_have_count(0)
