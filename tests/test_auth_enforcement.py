import os

os.environ["AUTH_DISABLED"] = "true"

import httpx
import pytest
from fastapi.testclient import TestClient

from app import app
from database import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_env():
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-32-chars-long-abcdef"
    await init_db()
    yield


def _register_and_login() -> str:
    """Register + login a real officer, returning a JWT access token."""
    reg = client.post(
        "/auth/register",
        json={
            "name": "Test Officer",
            "email": "enforce@test.gov.in",
            "password": "SecurePass123",
            "department": "Ministry of Defence",
        },
    )
    assert reg.status_code in (200, 409), reg.text
    login = client.post(
        "/auth/login",
        json={"email": "enforce@test.gov.in", "password": "SecurePass123"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _benchmark_payload() -> dict:
    return {
        "product_name": "A4 Paper 75gsm",
        "query_mode": "product",
        "department": "Ministry of Defence",
    }


@pytest.mark.asyncio
async def test_benchmark_requires_jwt_when_auth_enabled():
    from unittest.mock import patch

    with patch.dict(os.environ, {"AUTH_DISABLED": "false"}):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # No token -> 401
            r = await ac.post("/api/v1/benchmark", json=_benchmark_payload())
            assert r.status_code == 401
            assert r.json()["detail"] in (
                "Not authenticated",
                "Invalid or missing API key",
            )

            # Valid JWT -> 200
            token = _register_and_login()
            r2 = await ac.post(
                "/api/v1/benchmark",
                json=_benchmark_payload(),
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r2.status_code == 200, r2.text

            # Garbage token -> 401
            r3 = await ac.post(
                "/api/v1/benchmark",
                json=_benchmark_payload(),
                headers={"Authorization": "Bearer not-a-real-jwt"},
            )
            assert r3.status_code == 401


@pytest.mark.asyncio
async def test_reports_requires_jwt_when_auth_enabled():
    from unittest.mock import patch

    with patch.dict(os.environ, {"AUTH_DISABLED": "false"}):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as ac:
            r = await ac.post(
                "/api/v1/reports/generate", json={"search_id": "nonexistent"}
            )
            assert r.status_code == 401

            token = _register_and_login()
            r2 = await ac.post(
                "/api/v1/reports/generate",
                json={"search_id": "nonexistent"},
                headers={"Authorization": f"Bearer {token}"},
            )
            # Auth passes; search simply not found.
            assert r2.status_code == 404


@pytest.mark.asyncio
async def test_department_lpp_requires_jwt_when_auth_enabled():
    from unittest.mock import patch

    with patch.dict(os.environ, {"AUTH_DISABLED": "false"}):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as ac:
            r = await ac.get("/api/v1/department-lpp")
            assert r.status_code == 401

            token = _register_and_login()
            r2 = await ac.get(
                "/api/v1/department-lpp",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r2.status_code == 200, r2.text


@pytest.mark.asyncio
async def test_auth_disabled_allows_anonymous():
    import os as _os
    from unittest.mock import patch

    with patch.dict(_os.environ, {"AUTH_DISABLED": "true"}):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as ac:
            r = await ac.post("/api/v1/benchmark", json=_benchmark_payload())
            assert r.status_code == 200, r.text