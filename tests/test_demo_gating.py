"""Tests for demo-data integrity gating across the benchmark tiers.

Ensures seeded/demo records are explicitly flagged as is_demo_data and that
no service path fabricates REAL flags for demo records.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database import NotifiedRate
from services.gem_rate_lookup import check_gem_business_analytics, check_notified_rate
from services.tier_waterfall import get_price_benchmark


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _mock_session_for(rows: list) -> MagicMock:
    """Configure async_session_maker so `async with ... as session` yields a
    session whose `await session.execute(stmt)` returns a scalars() chain
    yielding the given rows. async_session_maker is an async context manager,
    so it is a plain MagicMock (not AsyncMock); session.execute must be an
    AsyncMock because the code awaits it. The execute result is a plain
    MagicMock (its .scalars() is synchronous)."""
    mock_session_maker = MagicMock()
    session = mock_session_maker.return_value.__aenter__.return_value
    mock_execute = MagicMock()
    mock_execute.scalars.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=mock_execute)
    return mock_session_maker


@pytest.mark.asyncio
async def test_notified_rate_demo_flag_defaults_to_true():
    """Newly seeded notified rates must default to is_demo_data=True."""
    rate = NotifiedRate(
        item_description="Cisco Catalyst 9300 switch",
        rate=150000.0,
        currency="INR",
        authority="DGS&D",
        contract_number="DGS&D/RC-2024/STN-0001",
        valid_from=_today(),
        valid_until=_today() + timedelta(days=365),
        is_active=True,
        unit="each",
        item_category="networking",
    )
    assert rate.is_demo_data is True


@pytest.mark.asyncio
async def test_check_notified_rate_returns_demo_flag():
    """check_notified_rate must surface the demo flag of the matched record."""
    today = _today()
    rate = NotifiedRate(
        item_description="Cisco Catalyst 9300 switch",
        rate=150000.0,
        currency="INR",
        authority="DGS&D",
        contract_number="DGS&D/RC-2024/STN-0001",
        valid_from=today - timedelta(days=30),
        valid_until=today + timedelta(days=300),
        is_active=True,
        is_demo_data=True,
        unit="each",
        item_category="networking",
    )

    with (
        patch(
            "services.gem_rate_lookup.async_session_maker",
            _mock_session_for([rate]),
        ),
        patch(
            "services.gem_rate_lookup.fuzz.token_set_ratio", return_value=95.0
        ) as mock_fuzz,
    ):
        result = await check_notified_rate("Cisco Catalyst 9300", category="networking")

        assert result is not None
        assert result["is_demo_data"] is True
        assert result["price"] == 150000.0
        mock_fuzz.assert_called()


@pytest.mark.asyncio
async def test_check_gem_lpp_returns_demo_flag_from_db():
    """GeM LPP lookup must propagate the stored demo flag (honest by default)."""
    gem_entry = type(
        "GemLPPCache",
        (),
        {
            "query_matched": "Cisco Catalyst 9300",
            "product_name": "Cisco Catalyst 9300",
            "lpp_price": 145000.0,
            "catalog_price": None,
            "source_url": "https://gem.gov.in/catalog/123",
            "gem_product_id": "GEM-123",
            "seller_name": "Test Seller",
            "specifications": {},
            "is_demo_data": True,
        },
    )()

    with (
        patch(
            "services.gem_rate_lookup.async_session_maker",
            _mock_session_for([gem_entry]),
        ),
        patch(
            "services.gem_rate_lookup.fuzz.token_set_ratio", return_value=90.0
        ) as mock_fuzz,
    ):
        result = await check_gem_business_analytics("Cisco Catalyst 9300")

        assert result is not None
        assert result["is_demo_data"] is True
        assert result["price"] == 145000.0
        mock_fuzz.assert_called()


@pytest.mark.asyncio
async def test_waterfall_primary_is_demo_surfaces_any_demo():
    """The waterfall result must let callers detect demo data in the primary."""
    mock_tier_0 = {
        "tier": 0,
        "price": 1000,
        "source": "Notified Rate",
        "is_demo_data": True,
    }

    with (
        patch(
            "services.tier_waterfall._check_tier_0", new_callable=AsyncMock
        ) as mock_0,
        patch(
            "services.tier_waterfall._check_tier_1", new_callable=AsyncMock
        ) as mock_1,
        patch(
            "services.tier_waterfall._check_tier_2", new_callable=AsyncMock
        ) as mock_2,
        patch("services.tier_waterfall._run_tier_3", new_callable=AsyncMock) as mock_3,
        patch("services.tier_waterfall._run_tier_4", new_callable=AsyncMock) as mock_4,
    ):
        mock_0.return_value = mock_tier_0
        mock_1.return_value = None
        mock_2.return_value = None
        mock_3.return_value = None
        mock_4.return_value = None

        result = await get_price_benchmark("laptop")

        assert result is not None
        assert result["resolved_tier"] == 0
        assert result["primary_result"]["is_demo_data"] is True
        assert result["primary_result"]["price"] == 1000


@pytest.mark.asyncio
async def test_waterfall_real_source_is_not_demo():
    """A genuinely uploaded/verified result must NOT be flagged as demo."""
    mock_tier_2 = {
        "tier": 2,
        "price": 1300,
        "source": "Dept PO",
        "is_demo_data": False,
    }

    with (
        patch(
            "services.tier_waterfall._check_tier_0", new_callable=AsyncMock
        ) as mock_0,
        patch(
            "services.tier_waterfall._check_tier_1", new_callable=AsyncMock
        ) as mock_1,
        patch(
            "services.tier_waterfall._check_tier_2", new_callable=AsyncMock
        ) as mock_2,
        patch("services.tier_waterfall._run_tier_3", new_callable=AsyncMock) as mock_3,
        patch("services.tier_waterfall._run_tier_4", new_callable=AsyncMock) as mock_4,
    ):
        mock_0.return_value = None
        mock_1.return_value = None
        mock_2.return_value = mock_tier_2
        mock_3.return_value = None
        mock_4.return_value = None

        result = await get_price_benchmark("laptop")

        assert result is not None
        assert result["resolved_tier"] == 2
        assert result["primary_result"]["is_demo_data"] is False
        assert result["primary_result"]["price"] == 1300
