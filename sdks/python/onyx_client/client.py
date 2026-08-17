from typing import Any

import httpx


class OnyxError(Exception):
    pass


class OnyxClient:
    """Synchronous client for the Onyx API."""

    def __init__(self, api_key: str, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {"x-api-key": self.api_key}
        self.client = httpx.Client(
            base_url=self.base_url, headers=self.headers, timeout=120.0
        )

    def fetch(self, url: str, **kwargs) -> dict[str, Any]:
        """Send a single fetch request."""
        payload = {"url": url}
        payload.update(kwargs)
        response = self.client.post("/fetch", json=payload)
        self._check_response(response)
        return response.json()

    # --- Price Benchmarking & Reports Endpoints ---
    def benchmark(
        self,
        product_name: str | None = None,
        quantity: int = 1,
        department: str | None = None,
        category: str | None = None,
        specs: dict | None = None,
        query: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        name = product_name or query
        if not name:
            raise ValueError("product_name is required for benchmarking")
        payload: dict[str, Any] = {"product_name": name, "quantity": quantity}
        if department:
            payload["department"] = department
        if category:
            payload["category"] = category
        if specs:
            payload["specs"] = specs
        payload.update(kwargs)
        response = self.client.post("/api/v1/benchmark", json=payload)
        self._check_response(response)
        return response.json()

    def generate_report(self, search_id: str) -> bytes:
        response = self.client.post(
            "/api/v1/reports/generate", json={"search_id": search_id}
        )
        self._check_response(response)
        return response.content

    def _check_response(self, response: httpx.Response):
        if not response.is_success:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise OnyxError(f"HTTP {response.status_code}: {detail}")


class AsyncOnyxClient:
    """Asynchronous client for the Onyx API."""

    def __init__(self, api_key: str, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {"x-api-key": self.api_key}
        self.client = httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers, timeout=120.0
        )

    async def fetch(self, url: str, **kwargs) -> dict[str, Any]:
        payload = {"url": url}
        payload.update(kwargs)
        response = await self.client.post("/fetch", json=payload)
        self._check_response(response)
        return response.json()

    async def benchmark(
        self,
        product_name: str | None = None,
        quantity: int = 1,
        department: str | None = None,
        category: str | None = None,
        specs: dict | None = None,
        query: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        name = product_name or query
        if not name:
            raise ValueError("product_name is required for benchmarking")
        payload: dict[str, Any] = {"product_name": name, "quantity": quantity}
        if department:
            payload["department"] = department
        if category:
            payload["category"] = category
        if specs:
            payload["specs"] = specs
        payload.update(kwargs)
        response = await self.client.post("/api/v1/benchmark", json=payload)
        self._check_response(response)
        return response.json()

    async def generate_report(self, search_id: str) -> bytes:
        response = await self.client.post(
            "/api/v1/reports/generate", json={"search_id": search_id}
        )
        self._check_response(response)
        return response.content

    def _check_response(self, response: httpx.Response):
        if not response.is_success:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise OnyxError(f"HTTP {response.status_code}: {detail}")
