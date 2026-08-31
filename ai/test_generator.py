"""Generates a pytest UI test skeleton from a plain-English user story, styled after this repo's
existing tests. Always review generated code before trusting it in CI - it's a starting point,
not a finished, verified test.
"""
from pathlib import Path

from ai.ollama_client import OllamaClient
from utils.logger import get_logger

logger = get_logger(__name__)

GENERATED_DIR = Path(__file__).parent.parent / "tests" / "ui" / "generated"

SPEC_SYSTEM_PROMPT = (
    "Convert the user's story into a structured test specification. "
    'Reply ONLY with JSON in this exact schema: {"title": "...", "steps": ["...", "...", ...]}. '
    "Steps must be short, imperative, action-oriented phrases (3-6 words each), not narrative "
    "sentences. Example for 'As a user, I want to log in with valid credentials': "
    '{"title": "Valid Login", "steps": ["Open Swag Labs", "Enter username", "Enter password", '
    '"Click login", "Verify Products page"]}'
)

SYSTEM_PROMPT = (
    "You generate a single pytest test function for a Playwright automation framework. "
    "Tests use a `page` fixture, import Page Objects from `pages.*` "
    "(available: LoginPage, InventoryPage, CartPage, CheckoutPage), and use plain `assert` "
    "statements. Reply with ONLY valid Python code - no markdown fences, no explanation."
)

EXAMPLE = """
import pytest
from pages.login_page import LoginPage

@pytest.mark.ui
def test_login_with_valid_user(page):
    login_page = LoginPage(page)
    login_page.open()
    login_page.login("standard_user", "secret_sauce")
    assert page.url.endswith("/inventory.html")
"""


def generate_test_spec(story: str) -> dict:
    """Converts a user story into a structured test specification (title + plain-English steps),
    without generating any code - the intermediate, human-reviewable artifact before generate_test()."""
    client = OllamaClient()
    spec = client.generate_json(story, system=SPEC_SYSTEM_PROMPT, timeout=120)
    logger.info(f"Generated test spec for story: {spec}")
    return spec


def generate_test(story: str, file_name: str) -> str:
    """Sends the story + a style example to the LLM and writes the generated test under tests/ui/generated/.

    Applies a small set of conservative post-processing transformations so generated tests better
    match the repository's Page Object API (adds missing LoginPage import, prefers get_title()/get_product_count()).
    """
    client = OllamaClient()
    prompt = (
        f"Existing test style example:\n{EXAMPLE}\n\n"
        f"Write ONE new pytest test function for this user story, following the same style:\n{story}"
    )
    code = client.generate(prompt, system=SYSTEM_PROMPT, timeout=120)
    code = code.strip().strip("`")
    if code.lower().startswith("python"):
        code = code[len("python"):].lstrip()

    # Small post-processing to reduce trivial incompatibilities with repository POMs
    # 1) Ensure LoginPage is imported when referenced
    if "LoginPage(" in code and "from pages.login_page import LoginPage" not in code:
        code = code.replace("from pages.inventory_page import InventoryPage\n", "from pages.inventory_page import InventoryPage\nfrom pages.login_page import LoginPage\n")

    # 2) Normalize common title/property usages to repository methods
    code = code.replace("inventory_page.is_title_present(\"Product Inventory\")", "inventory_page.get_title() == \"Products\"")
    code = code.replace("inventory_page.title", "inventory_page.get_title()")
    code = code.replace("inventory_page.product_list.count", "inventory_page.get_product_count()")

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = GENERATED_DIR / file_name
    header = "# AI-generated test (ai/test_generator.py) - review before relying on it.\n"
    out_path.write_text(header + code + "\n", encoding="utf-8")
    logger.info(f"Generated test written to {out_path}")
    return str(out_path)
