"""Explicit wait helpers layered on top of Playwright's built-in auto-waiting locators."""
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
