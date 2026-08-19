"""Tests for canonical base-product identity resolution (Q1/Q8)."""

from datetime import date

import pytest

from database import DepartmentPurchaseRecord, async_session_maker, init_db
from services.base_product import (
    canonicalize_product_name,
    count_base_products,
    resolve_base_product,
)
from services.department_lpp import normalize_item_key


@pytest.fixture(autouse=True)
async def _db():
    await init_db()
    yield


def _record(desc, price, department, when="2023-01-01"):
    return DepartmentPurchaseRecord(
        department=department,
        item_description=desc,
        normalized_item_key=normalize_item_key(desc),
        unit_price=float(price),
        quantity_purchased=1,
        purchase_date=date.fromisoformat(when),
        uploaded_by="tester",
    )


def test_canonicalize_product_name_fuzzy_collapse():
    from rapidfuzz import fuzz

    k1 = canonicalize_product_name("Cisco Catalyst 9300-48P-A Switch")
    k2 = canonicalize_product_name("Cisco 9300 48 Port Catalyst Switch")
    # The canonical keys are token-normalized; variant collapse happens via the
    # fuzzy identity matcher used by resolve_base_product (threshold >= 72).
    assert fuzz.token_set_ratio(k1, k2) >= 72


def test_count_base_products_collapses_variants():
    records = [
        {"item_description": "Cisco Catalyst 9300 Switch"},
        {"item_description": "Catalyst 9300 Cisco Switch"},
        {"item_description": "HP ProBook 450 G10 Notebook PC"},
    ]
    assert count_base_products(records) == 2


@pytest.mark.asyncio
async def test_resolve_base_product_matches_prior_records():
    async with async_session_maker() as session:
        session.add_all(
            [
                _record("HP ProBook 450 G10 Notebook PC", 74000, "Ministry of Defence"),
                _record("HP ProBook 450 G10 Notebook PC", 76000, "Ministry of Defence"),
            ]
        )
        await session.commit()

    bp = await resolve_base_product("hp probook 450", "Ministry of Defence")
    assert bp["prior_records"] == 2
    assert bp["prior_median_price"] == 75000.0
    assert bp["prior_min"] == 74000.0
    assert bp["prior_max"] == 76000.0
    assert bp["prior_departments"] == ["Ministry of Defence"]
    assert bp["canonical_key"] == canonicalize_product_name("hp probook 450")


@pytest.mark.asyncio
async def test_resolve_base_product_no_prior():
    bp = await resolve_base_product("space shuttle main engine", "Ministry of Defence")
    assert bp["prior_records"] == 0
    assert bp["prior_median_price"] is None
    assert bp["match_score"] is None


@pytest.mark.asyncio
async def test_resolve_base_product_scoped_by_department():
    async with async_session_maker() as session:
        session.add(
            _record("Cisco Catalyst 9300 Switch", 290000, "Ministry of Finance")
        )
        await session.commit()

    bp = await resolve_base_product("cisco catalyst 9300", "Ministry of Defence")
    assert bp["prior_records"] == 0  # no cross-department price leak