"""Sanity tests validating the framework's core wiring: config loading and browser/page fixtures."""
import pytest

from config.config_reader import ConfigReader


@pytest.mark.smoke
def test_config_loads():
    config = ConfigReader.get_config()
    assert "base_url" in config
    assert config.get("browser") in ("chromium", "firefox", "webkit")


@pytest.mark.ui
def test_browser_launches_and_navigates(page):
    page.goto("https://example.com")
    assert "Example" in page.title()
