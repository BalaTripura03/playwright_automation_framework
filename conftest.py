"""Root pytest fixtures wiring together BrowserManager, ContextManager and failure-reporting hooks."""
import pytest

from core.browser_manager import BrowserManager
from core.context_manager import ContextManager
from utils.logger import get_logger
from utils.screenshot_manager import capture_screenshot
from utils.trace_manager import start_trace, stop_trace

logger = get_logger(__name__)


@pytest.fixture(scope="session")
def browser_manager():
    """Starts one browser instance for the whole test session and closes it at the end."""
    manager = BrowserManager()
    manager.start()
    yield manager
    manager.stop()


@pytest.fixture
def context(browser_manager, request):
    """Provides a fresh, traced BrowserContext per test."""
    ctx_manager = ContextManager(browser_manager.browser)
    context = ctx_manager.create_context()
    start_trace(context)
    yield context
    stop_trace(context, request.node.name)
    ctx_manager.close_context()


@pytest.fixture
def page(context):
    """Provides a fresh Page per test, backed by the `context` fixture."""
    page = context.new_page()
    yield page
    page.close()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Captures a screenshot automatically whenever a test using the `page` fixture fails."""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        page = item.funcargs.get("page")
        if page:
            path = capture_screenshot(page, item.name)
            logger.info(f"Failure screenshot saved to {path}")
