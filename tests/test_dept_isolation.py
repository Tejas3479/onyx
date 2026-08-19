import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import app
from database import PriceSearch, User, async_session_maker, init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_env():
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-32-chars-long-abcdef"
    await init_db()
    yield


def _register_and_login(name: str, email: str, dept: str) -> str:
    reg = client.post(
        "/auth/register",
        json={
            "name": name,
            "email": email,
            "password": "SecurePass123",
            "department": dept,
        },
    )
    assert reg.status_code in (200, 409), reg.text
    login = client.post(
        "/auth/login", json={"email": email, "password": "SecurePass123"}
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


@pytest.mark.asyncio
async def test_price_history_scoped_by_department():
    """Non-admin officers must only see their own department's runs."""
    with patch.dict(os.environ, {"AUTH_DISABLED": "false"}):
        token_a = _register_and_login(
            "Officer A", "iso_a@mod.gov.in", "Ministry of Defence"
        )
        token_b = _register_and_login(
            "Officer B", "iso_b@fin.gov.in", "Ministry of Finance"
        )

        async with async_session_maker() as session:
            user_a = (
                await session.execute(
                    select(User).where(User.email == "iso_a@mod.gov.in")
                )
            ).scalars().first()
            user_b = (
                await session.execute(
                    select(User).where(User.email == "iso_b@fin.gov.in")
                )
            ).scalars().first()
            for u, q in (
                (user_a, "cisco router iso-a"),
                (user_b, "cisco router iso-b"),
            ):
                session.add(
                    PriceSearch(
                        id=str(uuid.uuid4()),
                        user_id=u.id,
                        query=q,
                        status="completed",
                        completed_at=datetime.now(timezone.utc),
                        resolved_tier=3,
                        tier_label="Market Survey",
                        query_mode="product",
                    )
                )
            await session.commit()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as ac:
            ra = await ac.get(
                "/api/v1/price-history?limit=100",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert ra.status_code == 200, ra.text
            items_a = [i["query"] for i in ra.json()["items"]]
            assert "cisco router iso-a" in items_a
            # Dept isolation: Finance runs must never leak into MoD's view
            assert not any("iso-b" in q for q in items_a)

            rb = await ac.get(
                "/api/v1/price-history?limit=100",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert rb.status_code == 200, rb.text
            items_b = [i["query"] for i in rb.json()["items"]]
            assert "cisco router iso-b" in items_b
            # MoD runs (incl. other MoD officers) must never leak into Finance's view
            assert not any("iso-a" in q for q in items_b)


@pytest.mark.asyncio
async def test_department_lpp_upload_enforces_scope():
    """Non-admins cannot ingest PO history for another department."""
    with patch.dict(os.environ, {"AUTH_DISABLED": "false"}):
        token_a = _register_and_login(
            "Officer A2", "iso_a2@mod.gov.in", "Ministry of Defence"
        )
        csv_content = (
            b"item_description,unit_price,quantity,purchase_date\n"
            b"UPS,20000,1,2023-01-01\n"
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as ac:
            r = await ac.post(
                "/api/v1/department-lpp/upload",
                data={"department": "Ministry of Finance"},
                files={"file": ("po.csv", csv_content, "text/csv")},
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert r.status_code == 403, r.text

            ok = await ac.post(
                "/api/v1/department-lpp/upload",
                data={"department": "Ministry of Defence"},
                files={"file": ("po.csv", csv_content, "text/csv")},
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert ok.status_code == 200, ok.text
            assert "compliance_warnings" in ok.json()
