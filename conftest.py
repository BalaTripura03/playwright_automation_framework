"""Root pytest fixtures wiring together BrowserManager, ContextManager and failure-reporting hooks."""
import pytest
import allure

from ai.bug_reporter import file_bug
from ai.root_cause_analyzer import analyze_failure
from config.config_reader import ConfigReader
from core.browser_manager import BrowserManager
from core.context_manager import ContextManager
from utils.logger import get_logger
from utils.screenshot_manager import capture_screenshot
from utils.trace_manager import start_trace, stop_trace

logger = get_logger(__name__)


def _attach_file(path: str, name: str, attachment_type):
    if not path:
        return
    try:
        allure.attach.file(path, name=name, attachment_type=attachment_type)
    except Exception as exc:
        logger.warning(f"Unable to attach {name} to Allure: {exc}")


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
    request.node._trace_path = None
    yield context
    if getattr(request.node, "_trace_path", None) is None:
        trace_path = stop_trace(context, request.node.name)
        request.node._trace_path = trace_path
    ctx_manager.close_context()


@pytest.fixture
def page(context):
    """Provides a fresh Page per test, backed by the `context` fixture."""
    page = context.new_page()
    yield page
    page.close()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """On failure: captures a screenshot, attaches the trace, then (if AI is enabled) runs
    root-cause analysis and auto-files a bug report when the local LLM is confident it's a real
    application bug."""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        context = item.funcargs.get("context")
        trace_path = getattr(item, "_trace_path", None)
        if context and not trace_path:
            trace_path = stop_trace(context, item.name)
            item._trace_path = trace_path
        if trace_path:
            _attach_file(trace_path, "Playwright Trace", allure.attachment_type.ZIP)

        if report.failed:
            page = item.funcargs.get("page")
            screenshot_path = None
            if page:
                screenshot_path = capture_screenshot(page, item.name)
                _attach_file(screenshot_path, "Failure Screenshot", allure.attachment_type.PNG)
                logger.info(f"Failure screenshot saved to {screenshot_path}")

            if ConfigReader.get("ai_enabled", False):
                try:
                    exception_text = str(call.excinfo.getrepr()) if call.excinfo else "Unknown exception"
                    analysis = analyze_failure(item.nodeid, exception_text)
                    file_bug(item.nodeid, analysis, evidence={"screenshot": screenshot_path})
                except Exception as e:
                    logger.error(f"AI failure-analysis pipeline errored (test result unaffected): {e}")
