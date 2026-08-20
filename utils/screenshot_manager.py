"""Captures Playwright screenshots and stores them under reports/screenshots for failure evidence."""
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page

SCREENSHOT_DIR = Path(__file__).parent.parent / "reports" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def capture_screenshot(page: Page, name: str) -> str:
    """Saves a full-page screenshot named '<name>_<timestamp>.png' and returns its path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)
    file_path = SCREENSHOT_DIR / f"{safe_name}_{timestamp}.png"
    page.screenshot(path=str(file_path), full_page=True)
    return str(file_path)
