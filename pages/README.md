# Pages

This folder holds the **Page Object Model (POM)** classes for the application under test.

## Convention

- One file per page/screen, e.g. `login_page.py`, `dashboard_page.py`.
- Every page class extends [`core/base_page.py`](../core/base_page.py)'s `BasePage`, which provides
  `navigate`, `click`, `fill`, `get_text`, `is_visible`, and `title` helpers built on Playwright locators.
- Keep selectors and page-specific actions inside the page class — tests should never contain raw
  CSS/XPath selectors.

## Example

```python
from core.base_page import BasePage


class LoginPage(BasePage):
    URL = "/login"
    USERNAME_INPUT = "#username"
    PASSWORD_INPUT = "#password"
    SUBMIT_BUTTON = "button[type='submit']"

    def open(self):
        self.navigate(self.URL)

    def login(self, username: str, password: str):
        self.fill(self.USERNAME_INPUT, username)
        self.fill(self.PASSWORD_INPUT, password)
        self.click(self.SUBMIT_BUTTON)
```

Tests then consume the page object via the `page` fixture from `conftest.py`:

```python
from pages.login_page import LoginPage


def test_login(page):
    login_page = LoginPage(page)
    login_page.open()
    login_page.login("user", "pass")
```
