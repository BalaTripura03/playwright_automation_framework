"""Page object for the Swag Labs cart screen (/cart.html)."""
from core.base_page import BasePage


class CartPage(BasePage):
    URL = "/cart.html"
    CART_ITEMS = ".cart_item"
    CHECKOUT_BUTTON = "#checkout"
    CONTINUE_SHOPPING_BUTTON = "#continue-shopping"

    def checkout(self):
        self.click(self.CHECKOUT_BUTTON)

    def get_item_count(self) -> int:
        return self.page.locator(self.CART_ITEMS).count()
