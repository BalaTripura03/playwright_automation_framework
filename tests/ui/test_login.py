"""UI tests for the Swag Labs login screen, covering valid, locked-out, and invalid credentials."""
import pytest

from pages.login_page import LoginPage
from utils.data_reader import read_json

users = read_json("saucedemo_users.json")


@pytest.mark.ui
@pytest.mark.smoke
def test_login_with_valid_user(page):
    login_page = LoginPage(page)
    login_page.open()
    login_page.login(users["valid_user"]["username"], users["valid_user"]["password"])

    assert page.url.endswith("/inventory.html")


@pytest.mark.ui
def test_login_with_locked_out_user(page):
    login_page = LoginPage(page)
    login_page.open()
    login_page.login(users["locked_user"]["username"], users["locked_user"]["password"])

    assert "locked out" in login_page.get_error_message().lower()


@pytest.mark.ui
def test_login_with_invalid_credentials(page):
    login_page = LoginPage(page)
    login_page.open()
    login_page.login(users["invalid_user"]["username"], users["invalid_user"]["password"])

    assert "do not match" in login_page.get_error_message().lower()
