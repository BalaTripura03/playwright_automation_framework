"""Creates/tears down Playwright BrowserContext objects using viewport and base_url from config."""
from playwright.sync_api import Browser, BrowserContext

from config.config_reader import ConfigReader
from utils.logger import get_logger

logger = get_logger(__name__)


class ContextManager:
    """Wraps browser.new_context() so every test gets an isolated context with consistent options."""

    def __init__(self, browser: Browser):
        self.browser = browser
        self.context: BrowserContext | None = None

    def create_context(self, **overrides) -> BrowserContext:
        options = {
            "viewport": {
                "width": ConfigReader.get("viewport_width", 1920),
                "height": ConfigReader.get("viewport_height", 1080),
            },
            "base_url": ConfigReader.get("base_url"),
            "ignore_https_errors": True,
        }
        options.update(overrides)
        self.context = self.browser.new_context(**options)
        self.context.set_default_timeout(ConfigReader.get("timeout", 30000))
        logger.info(f"Browser context created with options: {options}")
        return self.context

    def close_context(self):
        if self.context:
            self.context.close()
            logger.info("Browser context closed")
