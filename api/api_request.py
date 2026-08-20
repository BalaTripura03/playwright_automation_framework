"""Builder for reusable request definitions, kept separate from APIClient so payloads can be composed and shared."""
from api.api_client import APIClient
from api.api_response import APIResponse


class APIRequest:
    def __init__(self, endpoint: str, method: str = "GET"):
        self.endpoint = endpoint
        self.method = method.upper()
        self.headers: dict = {}
        self.params: dict = {}
        self.body = None

    def with_header(self, key: str, value: str) -> "APIRequest":
        self.headers[key] = value
        return self

    def with_headers(self, headers: dict) -> "APIRequest":
        self.headers.update(headers)
        return self

    def with_params(self, params: dict) -> "APIRequest":
        self.params.update(params)
        return self

    def with_body(self, body) -> "APIRequest":
        self.body = body
        return self

    def send(self, client: APIClient) -> APIResponse:
        return client._send(
            self.method,
            self.endpoint,
            params=self.params or None,
            json=self.body,
            headers=self.headers or None,
        )
