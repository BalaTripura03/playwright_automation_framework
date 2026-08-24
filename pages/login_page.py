"""Page object for the Swag Labs login screen (/)."""
from core.base_page import BasePage


class LoginPage(BasePage):
    URL = "/"
    USERNAME_INPUT = "#user-name"
    PASSWORD_INPUT = "#password"
    LOGIN_BUTTON = "#login-button"
    ERROR_MESSAGE = "[data-test='error']"

    # Fallback candidates used by self-healing locators if the primary selector ever breaks.
    USERNAME_CANDIDATES = ["#user-name", "input[name='user-name']", "input[placeholder='Username']"]
    PASSWORD_CANDIDATES = ["#password", "input[name='password']", "input[placeholder='Password']"]
    LOGIN_BUTTON_CANDIDATES = ["#login-button", "input[type='submit']", "button[type='submit']"]

    def open(self):
        self.navigate(self.URL)

    def login(self, username: str, password: str):
        self.smart_fill("login_username", self.USERNAME_CANDIDATES, username)
        self.smart_fill("login_password", self.PASSWORD_CANDIDATES, password)
        self.smart_click("login_button", self.LOGIN_BUTTON_CANDIDATES)

    def get_error_message(self) -> str:
        return self.get_text(self.ERROR_MESSAGE)
