import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app import app
from database import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_env():
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-32-chars-long-abcdef"
    os.environ["AUTH_DISABLED"] = "true"
    await init_db()
    yield


def _new_search_id() -> str:
    return str(uuid.uuid4())


def test_delegation_lifecycle():
    """Create, list, resolve, and audit a delegation for a benchmark run."""
    search_id = _new_search_id()

    r = client.post(
        "/api/v1/delegations",
        json={
            "search_id": search_id,
            "delegate_to_name": "Col. R. Sharma",
            "delegate_to_email": "sharma@mod.gov.in",
            "note": "Please review the L1 reasonableness band",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "open"
    assert body["delegate_to_name"] == "Col. R. Sharma"
    delegation_id = body["id"]

    listed = client.get(
        f"/api/v1/delegations?search_id={search_id}"
    ).json()
    assert len(listed) == 1
    assert listed[0]["status"] == "open"

    audit = client.get(f"/api/v1/audit?search_id={search_id}").json()
    actions = [e["action"] for e in audit]
    assert "benchmark_created" not in actions  # created only via benchmark router
    assert "delegated_for_review" in actions
    assert any("Delegated to Col. R. Sharma" in (e["note"] or "") for e in audit)

    resolved = client.post(
        f"/api/v1/delegations/{delegation_id}/resolve",
        json={"decision": "approved", "note": "Price within band"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["decision"] == "approved"

    listed2 = client.get(
        f"/api/v1/delegations?search_id={search_id}"
    ).json()
    assert listed2[0]["status"] == "completed"
    assert listed2[0]["decision"] == "approved"

    audit2 = client.get(f"/api/v1/audit?search_id={search_id}").json()
    assert any(e["action"] == "review_approved" for e in audit2)


def test_delegation_duplicate_resolution_conflict():
    """Resolving an already-completed delegation must 409."""
    search_id = _new_search_id()
    created = client.post(
        "/api/v1/delegations",
        json={"search_id": search_id, "delegate_to_name": "Ms. A. Verma"},
    ).json()
    delegation_id = created["id"]

    ok = client.post(
        f"/api/v1/delegations/{delegation_id}/resolve",
        json={"decision": "rejected", "note": "Evidence insufficient"},
    )
    assert ok.status_code == 200
    assert ok.json()["decision"] == "rejected"

    dup = client.post(
        f"/api/v1/delegations/{delegation_id}/resolve",
        json={"decision": "approved"},
    )
    assert dup.status_code == 409


def test_delegation_requires_valid_name():
    r = client.post(
        "/api/v1/delegations",
        json={"search_id": _new_search_id(), "delegate_to_name": ""},
    )
    assert r.status_code == 422


def test_audit_empty_for_unknown_run():
    audit = client.get(
        f"/api/v1/audit?search_id={_new_search_id()}"
    ).json()
    assert audit == []