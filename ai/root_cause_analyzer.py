"""Uses the local LLM (Ollama) to classify test failures and explain their likely root cause."""
from ai.ollama_client import OllamaClient
from utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a senior QA automation engineer. You will be given details about a failed "
    "Playwright test (test name, exception, and recent log lines). Classify the failure and "
    "reply ONLY with JSON in this exact schema: "
    '{"category": "app_bug|locator_issue|environment_issue|flaky_test", '
    '"confidence": 0-1, "explanation": "one or two sentences"}'
)


def analyze_failure(test_name: str, exception: str, logs: str = "", timeout: int = 120) -> dict:
    client = OllamaClient()
    # Keep the prompt small so the local model responds quickly - full traces aren't needed for classification.
    exception = exception[-1500:]
    logs = logs[-500:]
    prompt = f"Test: {test_name}\nException:\n{exception}\nRecent logs:\n{logs}"
    try:
        result = client.generate_json(prompt, system=SYSTEM_PROMPT, timeout=timeout)
    except Exception as e:
        logger.error(f"Root cause analysis unavailable (Ollama call failed): {e}")
        result = {}

    if not result:
        result = {"category": "unknown", "confidence": 0.0, "explanation": "AI analysis unavailable."}
    logger.info(f"Root cause analysis for {test_name}: {result}")
    return result
