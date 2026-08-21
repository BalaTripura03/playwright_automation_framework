"""Page object covering the Swag Labs checkout flow (steps one, two, and the completion screen)."""
from core.base_page import BasePage


class CheckoutPage(BasePage):
    FIRST_NAME_INPUT = "#first-name"
    LAST_NAME_INPUT = "#last-name"
    POSTAL_CODE_INPUT = "#postal-code"
    CONTINUE_BUTTON = "#continue"
    FINISH_BUTTON = "#finish"
    COMPLETE_HEADER = ".complete-header"
    SUMMARY_TOTAL_LABEL = ".summary_total_label"

    def fill_checkout_info(self, first_name: str, last_name: str, postal_code: str):
        self.fill(self.FIRST_NAME_INPUT, first_name)
        self.fill(self.LAST_NAME_INPUT, last_name)
        self.fill(self.POSTAL_CODE_INPUT, postal_code)
        self.click(self.CONTINUE_BUTTON)

    def get_total_label(self) -> str:
        return self.get_text(self.SUMMARY_TOTAL_LABEL)

    def finish(self):
        self.click(self.FINISH_BUTTON)

    def get_completion_message(self) -> str:
        return self.get_text(self.COMPLETE_HEADER)
