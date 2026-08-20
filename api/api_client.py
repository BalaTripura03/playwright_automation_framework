"""Thin wrapper around requests.Session providing base-URL resolution and request/response logging."""
import requests

from api.api_response import APIResponse
from config.config_reader import ConfigReader
from utils.logger import get_logger

logger = get_logger(__name__)


class APIClient:
    def __init__(self, base_url: str = None, headers: dict = None, timeout: int = 30):
        self.base_url = base_url or ConfigReader.get("api_base_url", ConfigReader.get("base_url", ""))
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(headers or {"Content-Type": "application/json", "Accept": "application/json"})

    def _url(self, endpoint: str) -> str:
        return endpoint if endpoint.startswith("http") else f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    def get(self, endpoint: str, params: dict = None, **kwargs) -> APIResponse:
        return self._send("GET", endpoint, params=params, **kwargs)

    def post(self, endpoint: str, json: dict = None, data=None, **kwargs) -> APIResponse:
        return self._send("POST", endpoint, json=json, data=data, **kwargs)

    def put(self, endpoint: str, json: dict = None, **kwargs) -> APIResponse:
        return self._send("PUT", endpoint, json=json, **kwargs)

    def patch(self, endpoint: str, json: dict = None, **kwargs) -> APIResponse:
        return self._send("PATCH", endpoint, json=json, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> APIResponse:
        return self._send("DELETE", endpoint, **kwargs)

    def _send(self, method: str, endpoint: str, **kwargs) -> APIResponse:
        url = self._url(endpoint)
        logger.info(f"API {method} -> {url}")
        response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        logger.info(f"API {method} <- {response.status_code} {url}")
        return APIResponse(response)
