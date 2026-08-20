"""Wraps a requests.Response with assertion helpers so tests read fluently."""
from requests import Response


class APIResponse:
    def __init__(self, response: Response):
        self.raw = response
        self.status_code = response.status_code
        try:
            self.body = response.json()
        except ValueError:
            self.body = response.text

    def assert_status(self, expected_status: int) -> "APIResponse":
        assert self.status_code == expected_status, (
            f"Expected status {expected_status} but got {self.status_code}. Body: {self.body}"
        )
        return self

    def json_path(self, *keys):
        """Traverses nested dict/list keys, e.g. response.json_path('data', 'id')."""
        value = self.body
        for key in keys:
            value = value[key]
        return value

    def assert_json_contains(self, key: str, expected_value) -> "APIResponse":
        actual = self.body.get(key) if isinstance(self.body, dict) else None
        assert actual == expected_value, f"Expected {key}={expected_value} but got {actual}"
        return self
