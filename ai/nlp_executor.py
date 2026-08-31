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


from utils.retry import smart_retry
from utils.waits import smart_wait
from core.locator_healer import SmartLocator


def _call_with_retry(fn, *a, **kw):
    # Wrap a call with the smart_retry decorator at runtime
    return smart_retry(max_attempts=3, backoff_seconds=0.5)(lambda: fn(*a, **kw))()


def _run_step(page, step: dict):
    action = step.get("action")
    args = step.get("args", {})

    if action == "login":
        def do_login():
            login_page = LoginPage(page)
            login_page.open()
            login_page.login(args.get("username"), args.get("password"))

        _call_with_retry(do_login)

    elif action == "verify_products":
        # Wait for product listing readiness using smart_wait and then assert
        def check_products():
            inventory_page = InventoryPage(page)
            smart_wait(page, lambda p: inventory_page.get_product_count() > 0, timeout=10000)
            assert inventory_page.get_title() == "Products", "Expected the Products page to be displayed"

        _call_with_retry(check_products)

    elif action == "add_to_cart":
        def do_add():
            InventoryPage(page).add_to_cart(args.get("product_slug"))

        _call_with_retry(do_add)

    elif action == "open_cart":
        def do_open_cart():
            # Use SmartLocator to try alternate selectors for the cart link if needed
            try:
                InventoryPage(page).open_cart()
            except Exception:
                # Attempt to heal: look for candidate selectors commonly used for cart link
                healer = SmartLocator(page, "cart_link", [".shopping_cart_link", ".cart-link", "#cart"] , timeout=2000)
                loc = healer.resolve()
                loc.click()

        _call_with_retry(do_open_cart)

    elif action == "checkout":
        _call_with_retry(lambda: CartPage(page).checkout())

    elif action == "fill_checkout_info":
        _call_with_retry(lambda: CheckoutPage(page).fill_checkout_info(args.get("first_name"), args.get("last_name"), args.get("postal_code")))

    elif action == "finish":
        _call_with_retry(lambda: CheckoutPage(page).finish())

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
