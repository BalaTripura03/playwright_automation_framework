"""Root pytest fixtures wiring together BrowserManager, ContextManager and failure-reporting hooks."""
import pytest

from ai.bug_reporter import file_bug
from ai.root_cause_analyzer import analyze_failure
from config.config_reader import ConfigReader
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
    """On failure: captures a screenshot, then (if AI is enabled) runs root-cause analysis and
    auto-files a bug report when the local LLM is confident it's a real application bug."""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        page = item.funcargs.get("page")
        screenshot_path = None
        if page:
            screenshot_path = capture_screenshot(page, item.name)
            logger.info(f"Failure screenshot saved to {screenshot_path}")

        if ConfigReader.get("ai_enabled", False):
            try:
                exception_text = str(call.excinfo.getrepr()) if call.excinfo else "Unknown exception"
                analysis = analyze_failure(item.nodeid, exception_text)
                file_bug(item.nodeid, analysis, evidence={"screenshot": screenshot_path})
            except Exception as e:
                logger.error(f"AI failure-analysis pipeline errored (test result unaffected): {e}")
