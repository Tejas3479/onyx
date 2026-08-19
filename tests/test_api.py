import os
from unittest.mock import patch

os.environ["AUTH_DISABLED"] = "true"

import httpx
import pytest
from fastapi.testclient import TestClient

from app import app
from database import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_env():
    os.environ["API_KEYS"] = "test-key"
    os.environ["DISABLE_SSRF_CHECK"] = "true"
    await init_db()
    yield
    if "API_KEYS" in os.environ:
        del os.environ["API_KEYS"]
    if "DISABLE_SSRF_CHECK" in os.environ:
        del os.environ["DISABLE_SSRF_CHECK"]


@pytest.fixture
async def async_client():
    from app import app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_curl_cffi_basic_fetch(async_client):
    headers = {"x-api-key": "test-key"}
    payload = {
        "url": "https://example.com",
        "output_format": "html",
        "render_js": False,
    }

    with patch("routers.fetch.DEMO_MODE", False):
        response = await async_client.post("/fetch", headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status_code"] == 200
    assert "Example Domain" in data["content"]


@pytest.mark.asyncio
async def test_markdown_output_clean(async_client):
    headers = {"x-api-key": "test-key"}
    payload = {
        "url": "https://example.com",
        "output_format": "markdown",
        "render_js": False,
    }

    with patch("routers.fetch.DEMO_MODE", False):
        response = await async_client.post("/fetch", headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    content = data["content"]
    assert "<script" not in content
    assert "<style" not in content
    assert len(content.strip()) > 0


@pytest.mark.asyncio
async def test_fetch_gated_in_demo_mode(async_client):
    """DEMO_MODE=true must short-circuit /fetch to a canned snapshot — no network."""
    headers = {"x-api-key": "test-key"}
    payload = {
        "url": "https://www.amazon.in/s?k=Cisco+Catalyst+9300",
        "output_format": "markdown",
        "render_js": True,
    }

    with patch("routers.fetch.DEMO_MODE", True):
        response = await async_client.post("/fetch", headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "DEMO MODE" in data["content"]
    assert "Cisco" in data["content"]


@pytest.mark.skip(reason="httpbin.org is currently flaky with 503 errors")
@pytest.mark.asyncio
async def test_session_cookie_persistence(async_client):
    headers = {"x-api-key": "test-key"}
    p1 = {
        "url": "https://httpbin.org/cookies/set?fetchtest=hello123",
        "session_id": "verify-session-001",
        "output_format": "html",
    }
    r1 = await async_client.post("/fetch", headers=headers, json=p1)
    assert r1.status_code == 200

    p2 = {
        "url": "https://httpbin.org/cookies",
        "session_id": "verify-session-001",
        "output_format": "html",
    }
    r2 = await async_client.post("/fetch", headers=headers, json=p2)
    assert r2.status_code == 200
    data = r2.json()
    assert "hello123" in data.get("content", "")


@pytest.mark.asyncio
async def test_session_list_and_delete(async_client):
    headers = {"x-api-key": "test-key"}
    # List
    r1 = await async_client.get("/api/sessions", headers=headers)
    assert r1.status_code == 200
    sessions = r1.json()
    assert isinstance(sessions, list)

    # Assuming verify-session-001 exists from previous test
    session_ids = [s["session_id"] for s in sessions]
    if "verify-session-001" in session_ids:
        r2 = await async_client.delete(
            "/api/sessions/verify-session-001", headers=headers
        )
        assert r2.status_code == 200

        r3 = await async_client.get("/api/sessions", headers=headers)
        session_ids_after = [s["session_id"] for s in r3.json()]
        assert "verify-session-001" not in session_ids_after


@pytest.mark.asyncio
async def test_proxy_routes(async_client):
    headers = {"x-api-key": "test-key"}
    proxy_url = "http://user:pass@10.0.0.1:8080"

    # 1. Add proxy
    r_add = await async_client.post(
        "/api/proxies", headers=headers, json={"url": proxy_url}
    )
    assert r_add.status_code == 200
    data_add = r_add.json()
    assert data_add["status"] == "added"
    assert "id" in data_add
    proxy_id = data_add["id"]

    # 2. Add same proxy again -> already_exists
    r_add_dup = await async_client.post(
        "/api/proxies", headers=headers, json={"url": proxy_url}
    )
    assert r_add_dup.status_code == 200
    data_dup = r_add_dup.json()
    assert data_dup["status"] == "already_exists"
    assert data_dup["id"] == proxy_id

    # 3. List proxies
    r_list = await async_client.get("/api/proxies", headers=headers)
    assert r_list.status_code == 200
    proxies = r_list.json()
    assert isinstance(proxies, list)
    matching = [p for p in proxies if p["id"] == proxy_id]
    assert len(matching) == 1
    assert matching[0]["url"] == proxy_url
    assert matching[0]["is_active"] is True
    assert matching[0]["fail_count"] == 0


@pytest.mark.asyncio
async def test_auth_modes(async_client):
    # Mode 1: x-api-key header
    r_header = await async_client.get("/api/proxies", headers={"x-api-key": "test-key"})
    assert r_header.status_code == 200

    # Mode 2: Authorization Bearer header
    r_bearer = await async_client.get(
        "/api/proxies", headers={"Authorization": "Bearer test-key"}
    )
    assert r_bearer.status_code == 200

    # Mode 3: Database-backed API key
    from database import ApiKey, async_session_maker

    async with async_session_maker() as session:
        session.add(ApiKey(key="db-test-key-001", name="test db key"))
        await session.commit()

    r_db_key = await async_client.get(
        "/api/proxies", headers={"x-api-key": "db-test-key-001"}
    )
    assert r_db_key.status_code == 200

    r_db_bearer = await async_client.get(
        "/api/proxies",
        headers={"Authorization": "Bearer db-test-key-001"},
    )
    assert r_db_bearer.status_code == 200

    # Mode 4: Missing or invalid API key -> 401
    r_missing = await async_client.get("/api/proxies")
    assert r_missing.status_code == 401
    assert r_missing.json()["detail"] == "Invalid or missing API key"

    r_invalid = await async_client.get(
        "/api/proxies", headers={"x-api-key": "wrong-key-999"}
    )
    assert r_invalid.status_code == 401
    assert r_invalid.json()["detail"] == "Invalid or missing API key"

    # Mode 5: AUTH_DISABLED=true with empty VALID_KEYS and no DB keys
    from sqlalchemy import delete

    import auth

    async with async_session_maker() as session:
        await session.execute(delete(ApiKey))
        await session.commit()

    with (
        patch.object(auth, "VALID_KEYS", set()),
        patch.dict(os.environ, {"AUTH_DISABLED": "true"}),
    ):
        r_disabled = await async_client.get("/api/proxies")
        assert r_disabled.status_code == 200
