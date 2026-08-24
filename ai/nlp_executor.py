"""Executes a plain-English instruction by mapping it (via the local LLM) to a fixed, auditable
vocabulary of page actions - the model chooses from a known action set, it never generates or
runs arbitrary code, which keeps NLP-driven execution safe and deterministic.
"""
from ai.ollama_client import OllamaClient
from pages.cart_page import CartPage
from pages.checkout_page import CheckoutPage
from pages.inventory_page import InventoryPage
from pages.login_page import LoginPage
from utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "Convert the user's instruction into a JSON plan using ONLY these actions: "
    "login(username, password), verify_products(), add_to_cart(product_slug), open_cart(), "
    "checkout(), fill_checkout_info(first_name, last_name, postal_code), finish(). "
    'Reply ONLY with JSON: {"steps": [{"action": "...", "args": {...}}, ...]}'
)


def _run_step(page, step: dict):
    action = step.get("action")
    args = step.get("args", {})

    if action == "login":
        login_page = LoginPage(page)
        login_page.open()
        login_page.login(args["username"], args["password"])
    elif action == "verify_products":
        inventory_page = InventoryPage(page)
        assert inventory_page.get_title() == "Products", "Expected the Products page to be displayed"
    elif action == "add_to_cart":
        InventoryPage(page).add_to_cart(args["product_slug"])
    elif action == "open_cart":
        InventoryPage(page).open_cart()
    elif action == "checkout":
        CartPage(page).checkout()
    elif action == "fill_checkout_info":
        CheckoutPage(page).fill_checkout_info(args["first_name"], args["last_name"], args["postal_code"])
    elif action == "finish":
        CheckoutPage(page).finish()
    else:
        raise ValueError(f"Unknown action from NLP plan: {action}")


def execute_instruction(page, instruction: str) -> list[dict]:
    """Parses `instruction` into a step plan via the LLM, then executes each step against `page`."""
    client = OllamaClient()
    plan = client.generate_json(instruction, system=SYSTEM_PROMPT, timeout=120)
    steps = plan.get("steps", [])
    logger.info(f"NLP plan for '{instruction}': {steps}")
    for step in steps:
        _run_step(page, step)
    return steps
