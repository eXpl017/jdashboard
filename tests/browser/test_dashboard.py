from __future__ import annotations

import re
from typing import Any

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui


def _wait_dashboard_ready(page: Page) -> None:
    page.goto("/")
    expect(page.locator(".job-card")).not_to_have_count(0)
    expect(page.locator("#stat-total-jobs")).not_to_have_text("—")


def _active_filters(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """
        () => ({
          q: document.getElementById("filter-q")?.value ?? "",
          source: document.getElementById("filter-source")?.value ?? "",
          role: document.getElementById("filter-role")?.value ?? "",
          language: document.getElementById("filter-language")?.value ?? "",
          location: document.getElementById("filter-location")?.value ?? "",
          location_scope: document.getElementById("filter-location-scope")?.value ?? "",
          remote: document.getElementById("filter-remote")?.value ?? "",
          visa: document.getElementById("filter-visa")?.value ?? "",
          tag: document.getElementById("filter-tag")?.value ?? "",
          days: document.getElementById("filter-days")?.value ?? "",
          sort: document.getElementById("filter-sort")?.value ?? "",
          include_active: document.getElementById("filter-include-active")?.checked ?? false,
        })
        """
    )


def test_dashboard_elements_present(page: Page, base_url: str) -> None:
    page.goto(base_url + "/")

    expect(page.get_by_role("heading", level=1, name="Japan Cybersecurity Jobs")).to_be_visible()
    expect(page.locator(".app-header__subtitle")).to_contain_text("Public listings from")
    expect(page.locator(".summary-card")).to_have_count(4)
    expect(page.locator("#stat-total-jobs")).to_be_visible()
    expect(page.locator("#stat-new-in-window")).to_be_visible()
    expect(page.locator("#stat-sources-healthy")).to_be_visible()
    expect(page.locator("#stat-last-run")).to_be_visible()

    for control_id in [
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
        "filters-clear",
    ]:
        expect(page.locator(f"#{control_id}")).to_be_visible()

    expect(page.locator("#job-list")).to_be_visible()
    expect(page.locator("#refresh-panel")).to_be_visible()
    expect(page.locator("#refresh-status-line")).to_be_visible()
    expect(page.locator("#refresh-source-list")).to_be_visible()
    expect(page.locator("footer.app-footer")).to_contain_text("Refreshes run only when you press")


def test_default_view_shows_technical_japan_jobs_and_url_state(page: Page, base_url: str) -> None:
    _wait_dashboard_ready(page)

    filters = _active_filters(page)
    assert filters["role"] == "technical"
    assert filters["location_scope"] == "japan"
    assert filters["days"] == "3"
    assert filters["sort"] == "posted_desc"
    assert filters["include_active"] is False

    # Default filter values are reflected in the URL state.
    assert "role=technical" in page.url
    assert "location_scope=japan" in page.url
    assert "days=3" in page.url
    assert "sort=posted_desc" in page.url

    cards = page.locator(".job-card")
    expect(cards).to_have_count(3)
    titles = cards.locator(".job-card__title a").all_text_contents()
    assert "Cloud Security Engineer" in titles
    assert "SOC Analyst" in titles
    assert "Application Security Engineer" in titles
    assert "GRC Specialist" not in titles
    assert "Security Engineer (Global Remote)" not in titles

    expect(page.locator("#stat-total-jobs")).to_have_text("3")


def test_filter_changes_update_results_and_url(page: Page, base_url: str) -> None:
    _wait_dashboard_ready(page)

    page.locator("#filter-role").select_option("grc")
    expect(page.locator(".job-card")).to_have_count(1)
    expect(page.locator(".job-card__title a").first).to_have_text("GRC Specialist")
    expect(page).to_have_url(re.compile(r"[?&]role=grc(&|$)"))

    page.locator("#filter-role").select_option("all")
    page.locator("#filter-location-scope").select_option("international_remote")
    expect(page.locator(".job-card")).to_have_count(1)
    expect(page.locator(".job-card__title a").first).to_have_text(
        "Security Engineer (Global Remote)"
    )
    expect(page).to_have_url(re.compile(r"[?&]location_scope=international_remote(&|$)"))

    page.locator("#filters-clear").click()
    expect(page.locator(".job-card")).to_have_count(3)
    filters = _active_filters(page)
    assert filters["role"] == "technical"
    assert filters["location_scope"] == "japan"
    assert "role=technical" in page.url
    assert "location_scope=japan" in page.url


def test_search_and_other_filters_work(page: Page, base_url: str) -> None:
    _wait_dashboard_ready(page)

    page.locator("#filter-q").fill("Kabu")
    expect(page.locator(".job-card")).to_have_count(1)
    expect(page.locator(".job-card__title a").first).to_have_text("Cloud Security Engineer")

    page.locator("#filters-clear").click()
    expect(page.locator(".job-card")).to_have_count(3)

    page.locator("#filter-source").select_option("daijob")
    expect(page.locator(".job-card")).to_have_count(1)
    expect(page.locator(".job-card__title a").first).to_have_text("Application Security Engineer")

    page.locator("#filters-clear").click()
    page.locator("#filter-language").select_option("ja")
    expect(page.locator(".job-card")).to_have_count(2)
    titles = page.locator(".job-card__title a").all_text_contents()
    assert "SOC Analyst" in titles
    assert "Cloud Security Engineer" in titles

    page.locator("#filters-clear").click()
    page.locator("#filter-remote").select_option("remote")
    expect(page.locator(".job-card")).to_have_count(1)
    expect(page.locator(".job-card__title a").first).to_have_text("Application Security Engineer")

    page.locator("#filters-clear").click()
    page.locator("#filter-visa").select_option("overseas")
    expect(page.locator(".job-card")).to_have_count(1)
    expect(page.locator(".job-card__title a").first).to_have_text("Application Security Engineer")


def test_job_cards_show_output_and_badges(page: Page, base_url: str) -> None:
    _wait_dashboard_ready(page)

    eng = page.locator(".job-card", has=page.get_by_role("link", name="Cloud Security Engineer"))
    expect(eng).to_have_count(1)
    expect(eng.locator(".job-card__company")).to_have_text("Kabu Security")
    expect(eng.locator(".job-card__location")).to_contain_text("Tokyo")
    expect(eng.locator(".job-card__salary")).not_to_be_empty()
    expect(eng.locator(".job-card__source")).to_have_text("JapanDev")
    expect(eng.locator(".job-card__posted")).not_to_be_empty()

    badges = eng.locator(".job-card__badges .badge")
    badge_texts = badges.all_text_contents()
    assert "EN/JA" in badge_texts
    assert "Hybrid" in badge_texts
    assert "Japan · hybrid" in badge_texts
    assert "Japan residents only" in badge_texts
    assert "cloud-security" in badge_texts

    link = eng.locator(".job-card__link")
    expect(link).to_have_attribute("href", "https://example.com/jobs/eng")
    expect(link).to_have_attribute("target", "_blank")

    # Details toggle
    expect(eng.locator(".job-card__description")).not_to_be_visible()
    eng.locator("summary").click()
    expect(eng.locator(".job-card__description")).to_be_visible()
    expect(eng.locator(".job-card__description")).to_contain_text(
        "Build and secure cloud infrastructure"
    )

    remote_jp = page.locator(
        ".job-card",
        has=page.get_by_role("link", name="Application Security Engineer"),
    )
    remote_badges = remote_jp.locator(".job-card__badges .badge").all_text_contents()
    assert "Overseas eligible" in remote_badges

    page.locator("#filter-role").select_option("all")
    page.locator("#filter-location-scope").select_option("international_remote")
    intl = page.locator(
        ".job-card",
        has=page.get_by_role("link", name="Security Engineer (Global Remote)"),
    )
    expect(intl).to_have_count(1)
    intl_badges = intl.locator(".job-card__badges .badge").all_text_contents()
    assert "International remote" in intl_badges
    assert "Overseas eligible" in intl_badges
