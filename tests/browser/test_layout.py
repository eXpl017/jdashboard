from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui


def _wait_ready(page: Page) -> None:
    page.goto("/")
    expect(page.locator(".job-card")).not_to_have_count(0)


def _assert_no_horizontal_overflow(page: Page) -> None:
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
    )
    assert overflow is False


def _assert_no_element_overlap(page: Page, selector: str) -> None:
    overlaps = page.evaluate(
        """
        (selector) => {
          const els = Array.from(document.querySelectorAll(selector)).filter((el) => {
            const r = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return (
              r.width > 0 &&
              r.height > 0 &&
              style.visibility !== 'hidden' &&
              style.display !== 'none'
            );
          });
          for (let i = 0; i < els.length; i++) {
            const a = els[i].getBoundingClientRect();
            for (let j = i + 1; j < els.length; j++) {
              const b = els[j].getBoundingClientRect();
              const overlapX = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
              const overlapY = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
              if (overlapX > 1 && overlapY > 1) return true;
            }
          }
          return false;
        }
        """,
        selector,
    )
    assert overlaps is False


def test_no_overlap_desktop(page: Page, base_url: str) -> None:
    page.set_viewport_size({"width": 1280, "height": 900})
    _wait_ready(page)
    _assert_no_horizontal_overflow(page)
    _assert_no_element_overlap(page, ".job-card")
    _assert_no_element_overlap(page, ".summary-card")
    _assert_no_element_overlap(page, ".filters .field")


def test_no_overlap_mobile(page: Page, base_url: str) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    _wait_ready(page)
    _assert_no_horizontal_overflow(page)
    _assert_no_element_overlap(page, ".job-card")
    _assert_no_element_overlap(page, ".summary-card")
    expect(page.locator(".app-header__inner")).to_be_visible()


def test_dark_mode_uses_dark_theme_colors(browser, base_url: str) -> None:
    context = browser.new_context(color_scheme="dark", viewport={"width": 1280, "height": 900})
    page = context.new_page()
    try:
        page.goto(base_url + "/")
        expect(page.locator(".job-card")).not_to_have_count(0)
        colors = page.evaluate(
            """
            () => {
              const root = getComputedStyle(document.documentElement);
              const body = getComputedStyle(document.body);
              return {
                bg: root.getPropertyValue('--bg').trim().toLowerCase(),
                text: root.getPropertyValue('--text').trim().toLowerCase(),
                bodyBg: body.backgroundColor,
                bodyColor: body.color,
              };
            }
            """
        )
        assert colors["bg"] == "#0f1216"
        assert colors["text"] == "#e8ebf0"
        # body should reflect dark background (rgb(15, 18, 22))
        assert "15" in colors["bodyBg"] and "18" in colors["bodyBg"] and "22" in colors["bodyBg"]
    finally:
        context.close()


def test_light_mode_uses_light_theme_colors(browser, base_url: str) -> None:
    context = browser.new_context(color_scheme="light", viewport={"width": 1280, "height": 900})
    page = context.new_page()
    try:
        page.goto(base_url + "/")
        expect(page.locator(".job-card")).not_to_have_count(0)
        colors = page.evaluate(
            """
            () => {
              const root = getComputedStyle(document.documentElement);
              return {
                bg: root.getPropertyValue('--bg').trim().toLowerCase(),
                text: root.getPropertyValue('--text').trim().toLowerCase(),
              };
            }
            """
        )
        assert colors["bg"] == "#f6f7f9"
        assert colors["text"] == "#18202a"
    finally:
        context.close()
