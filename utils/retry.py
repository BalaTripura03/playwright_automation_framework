"""Retry decorator for transient Playwright/network failures. Does not swallow real assertion failures."""
import functools
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from utils.logger import get_logger

logger = get_logger(__name__)

TRANSIENT_EXCEPTIONS = (PlaywrightTimeoutError, ConnectionError, TimeoutError)


def smart_retry(max_attempts: int = 3, backoff_seconds: float = 1.0, exceptions=TRANSIENT_EXCEPTIONS):
    """Retries the decorated function on transient exceptions only, with exponential backoff."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 1
            delay = backoff_seconds
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt >= max_attempts:
                        logger.error(f"{func.__name__} failed after {attempt} attempts: {e}")
                        raise
                    logger.warning(f"{func.__name__} attempt {attempt} failed ({e}); retrying in {delay}s")
                    time.sleep(delay)
                    attempt += 1
                    delay *= 2

        return wrapper

    return decorator
