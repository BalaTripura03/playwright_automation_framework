"""Explicit wait helpers layered on top of Playwright's built-in auto-waiting locators."""
import time

from playwright.sync_api import Locator, Page, expect

DEFAULT_TIMEOUT = 10000


def wait_for_visible(locator: Locator, timeout: int = DEFAULT_TIMEOUT):
    expect(locator).to_be_visible(timeout=timeout)


def wait_for_hidden(locator: Locator, timeout: int = DEFAULT_TIMEOUT):
    expect(locator).to_be_hidden(timeout=timeout)


def wait_for_enabled(locator: Locator, timeout: int = DEFAULT_TIMEOUT):
    expect(locator).to_be_enabled(timeout=timeout)


def wait_for_text(locator: Locator, text: str, timeout: int = DEFAULT_TIMEOUT):
    expect(locator).to_contain_text(text, timeout=timeout)


def wait_for_url(page: Page, url_pattern, timeout: int = DEFAULT_TIMEOUT):
    page.wait_for_url(url_pattern, timeout=timeout)


def wait_for_load_state(page: Page, state: str = "networkidle", timeout: int = DEFAULT_TIMEOUT):
    page.wait_for_load_state(state, timeout=timeout)


def smart_wait(page: Page, condition, timeout: int = 15000, poll_interval: int = 250):
    """Polls `condition(page) -> bool` until it's true, instead of waiting a fixed duration.

    Use this for app-specific readiness signals that don't map to a single element state,
    e.g. `smart_wait(page, lambda p: p.locator('.cart_badge').inner_text() == '2')`.
    """
    start = time.time()
    while (time.time() - start) * 1000 < timeout:
        try:
            if condition(page):
                return True
        except Exception:
            pass
        page.wait_for_timeout(poll_interval)
    raise TimeoutError(f"smart_wait condition not met within {timeout}ms")
