"""UI test covering the full Swag Labs purchase flow: login -> add to cart -> checkout -> confirmation."""
import pytest

from pages.cart_page import CartPage
from pages.checkout_page import CheckoutPage
from pages.inventory_page import InventoryPage
from pages.login_page import LoginPage
from utils.data_reader import read_json

data = read_json("saucedemo_users.json")


@pytest.mark.ui
@pytest.mark.regression
def test_end_to_end_checkout(page):
    login_page = LoginPage(page)
    login_page.open()
    login_page.login(data["valid_user"]["username"], data["valid_user"]["password"])

    inventory_page = InventoryPage(page)
    inventory_page.add_to_cart("sauce-labs-backpack")
    inventory_page.add_to_cart("sauce-labs-bike-light")
    assert inventory_page.get_cart_count() == 2

    inventory_page.open_cart()
    cart_page = CartPage(page)
    assert cart_page.get_item_count() == 2
    cart_page.checkout()

    checkout_page = CheckoutPage(page)
    info = data["checkout_info"]
    checkout_page.fill_checkout_info(info["first_name"], info["last_name"], info["postal_code"])
    assert "total" in checkout_page.get_total_label().lower()

    checkout_page.finish()
    assert "thank you" in checkout_page.get_completion_message().lower()
