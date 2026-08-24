"""Page object for the Swag Labs product listing screen (/inventory.html)."""
from core.base_page import BasePage
from utils.waits import smart_wait


class InventoryPage(BasePage):
    URL = "/inventory.html"
    PAGE_TITLE = ".title"
    INVENTORY_ITEMS = ".inventory_item"
    PRODUCT_NAMES = ".inventory_item_name"
    CART_BADGE = ".shopping_cart_badge"
    CART_LINK = ".shopping_cart_link"
    SORT_DROPDOWN = ".product_sort_container"
    MENU_BUTTON = "#react-burger-menu-btn"
    LOGOUT_LINK = "#logout_sidebar_link"

    def add_to_cart(self, product_slug: str):
        self.click(f"#add-to-cart-{product_slug}")

    def remove_from_cart(self, product_slug: str):
        self.click(f"#remove-{product_slug}")

    def get_product_count(self) -> int:
        return self.page.locator(self.INVENTORY_ITEMS).count()

    def get_product_names(self) -> list[str]:
        return self.page.locator(self.PRODUCT_NAMES).all_inner_texts()

    def get_cart_count(self) -> int:
        if self.is_visible(self.CART_BADGE):
            return int(self.get_text(self.CART_BADGE))
        return 0

    def wait_for_cart_count(self, expected: int, timeout: int = 5000):
        """Dynamic wait: polls the cart badge until it reflects the expected count, instead of a fixed sleep."""
        smart_wait(self.page, lambda p: self.get_cart_count() == expected, timeout=timeout)

    def open_cart(self):
        self.click(self.CART_LINK)

    def get_title(self) -> str:
        return self.get_text(self.PAGE_TITLE)

    def sort_by(self, option_value: str):
        self.page.locator(self.SORT_DROPDOWN).select_option(option_value)

    def logout(self):
        self.click(self.MENU_BUTTON)
        self.click(self.LOGOUT_LINK)
