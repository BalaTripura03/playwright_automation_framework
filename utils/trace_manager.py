"""Starts/stops Playwright tracing so trace .zip files can be inspected in trace.playwright.dev."""
from pathlib import Path

from playwright.sync_api import BrowserContext

TRACE_DIR = Path(__file__).parent.parent / "reports" / "traces"
TRACE_DIR.mkdir(parents=True, exist_ok=True)


def start_trace(context: BrowserContext):
    context.tracing.start(screenshots=True, snapshots=True, sources=True)


def stop_trace(context: BrowserContext, name: str) -> str:
    """Stops tracing and saves the trace as '<name>.zip' under reports/traces."""
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)
    trace_path = TRACE_DIR / f"{safe_name}.zip"
    context.tracing.stop(path=str(trace_path))
    return str(trace_path)
