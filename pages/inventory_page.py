"""Page object for the Swag Labs product listing screen (/inventory.html)."""
from core.base_page import BasePage


class InventoryPage(BasePage):
    URL = "/inventory.html"
    PAGE_TITLE = ".title"
    INVENTORY_ITEMS = ".inventory_item"
    CART_BADGE = ".shopping_cart_badge"
    CART_LINK = ".shopping_cart_link"
    SORT_DROPDOWN = ".product_sort_container"

    def add_to_cart(self, product_slug: str):
        self.click(f"#add-to-cart-{product_slug}")

    def remove_from_cart(self, product_slug: str):
        self.click(f"#remove-{product_slug}")

    def get_cart_count(self) -> int:
        if self.is_visible(self.CART_BADGE):
            return int(self.get_text(self.CART_BADGE))
        return 0

    def open_cart(self):
        self.click(self.CART_LINK)

    def get_title(self) -> str:
        return self.get_text(self.PAGE_TITLE)

    def sort_by(self, option_value: str):
        self.page.locator(self.SORT_DROPDOWN).select_option(option_value)
