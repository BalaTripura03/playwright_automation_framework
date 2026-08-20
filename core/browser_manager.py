"""Starts the Playwright engine and launches/closes the browser type configured in config.yaml."""
from playwright.sync_api import Browser, Playwright, sync_playwright

from config.config_reader import ConfigReader
from utils.logger import get_logger

logger = get_logger(__name__)


class BrowserManager:
    """Owns the Playwright driver process and the single Browser instance for a test session."""

    def __init__(self):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    def start(self) -> Browser:
        browser_type = ConfigReader.get("browser", "chromium").lower()
        headless = ConfigReader.get("headless", True)
        slow_mo = ConfigReader.get("slow_mo", 0)

        logger.info(f"Launching {browser_type} browser (headless={headless}, slow_mo={slow_mo})")
        self._playwright = sync_playwright().start()
        launcher = getattr(self._playwright, browser_type)
        self._browser = launcher.launch(headless=headless, slow_mo=slow_mo)
        return self._browser

    @property
    def browser(self) -> Browser:
        return self._browser

    def stop(self):
        if self._browser:
            self._browser.close()
            logger.info("Browser closed")
        if self._playwright:
            self._playwright.stop()
