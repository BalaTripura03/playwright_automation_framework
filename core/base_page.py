"""Base Page Object with common interactions that every concrete page class in pages/ inherits."""
from playwright.sync_api import Page

from core.locator_healer import SmartLocator
from utils.logger import get_logger
from utils.retry import smart_retry
from utils.waits import wait_for_visible

logger = get_logger(__name__)


class BasePage:
    def __init__(self, page: Page):
        self.page = page

    def navigate(self, url: str):
        logger.info(f"Navigating to {url}")
        self.page.goto(url)

    @smart_retry(max_attempts=2)
    def click(self, selector: str):
        locator = self.page.locator(selector)
        wait_for_visible(locator)
        locator.click()

    @smart_retry(max_attempts=2)
    def fill(self, selector: str, value: str):
        locator = self.page.locator(selector)
        wait_for_visible(locator)
        locator.fill(value)

    def smart_click(self, key: str, candidates: list[str]):
        """Self-healing click: tries each candidate selector, healing onto whichever one resolves."""
        SmartLocator(self.page, key, candidates).resolve().click()

    def smart_fill(self, key: str, candidates: list[str], value: str):
        """Self-healing fill: tries each candidate selector, healing onto whichever one resolves."""
        SmartLocator(self.page, key, candidates).resolve().fill(value)

    def get_text(self, selector: str) -> str:
        return self.page.locator(selector).inner_text()

    def is_visible(self, selector: str) -> bool:
        return self.page.locator(selector).is_visible()

    def title(self) -> str:
        return self.page.title()
