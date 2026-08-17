"""Tests for Tier 3 demo-mode behavior.

Covers:
  - Fuzzy demo-cache matching (hero query "S-band Software Defined Radio" ->
    cache key "software defined radio")
  - DEMO_MODE short-circuit: never touches the network, returns cache
  - DEMO_MODE with no cache hit returns []
  - Tier 3 now runs for service queries
"""

from unittest.mock import AsyncMock, patch

import pytest

from services.search_orchestrator import (
    _check_demo_cache,
    run_market_survey,
)
from services.tier_waterfall import get_price_benchmark

DEMO_CACHE = {
    "software defined radio": [
        {
            "product_name": "Ettus USRP B210 Software Defined Radio",
            "price": 178500.0,
            "currency": "INR",
            "source_name": "National Instruments India",
            "source_url": "https://www.ni.com/en-in/shop/select/usrp-software-defined-radio-device",
            "confidence": "HIGH",
            "reliability": "HIGH",
            "is_demo_data": True,
        }
    ],
    "cisco catalyst 9300": [
        {
            "product_name": "Cisco Catalyst 9300 switch",
            "price": 278000.0,
            "currency": "INR",
            "source_name": "GeM",
            "source_url": "https://gem.gov.in",
            "confidence": "HIGH",
            "reliability": "HIGH",
            "is_demo_data": True,
        }
    ],
}


@pytest.fixture(autouse=True)
def _patch_cache_path(monkeypatch, tmp_path):
    cache_file = tmp_path / "demo_cache.json"
    import json

    cache_file.write_text(json.dumps(DEMO_CACHE), encoding="utf-8")
    monkeypatch.setattr("services.search_orchestrator.DEMO_CACHE_PATH", cache_file)


def test_fuzzy_match_hero_sdr_query():
    """'S-band Software Defined Radio' must fuzzy-match the cache key."""
    result = _check_demo_cache("S-band Software Defined Radio")
    assert result is not None
    assert result[0]["product_name"].startswith("Ettus USRP B210")


def test_exact_match():
    result = _check_demo_cache("software defined radio")
    assert result is not None
    assert result[0]["is_demo_data"] is True


def test_prefix_match():
    result = _check_demo_cache("cisco catalyst 9300 48-port switch")
    assert result is not None
    assert result[0]["price"] == 278000.0


def test_no_match_returns_none():
    assert _check_demo_cache("quantum entangled toaster") is None


@pytest.mark.asyncio
async def test_demo_mode_skips_network_and_serves_cache(monkeypatch):
    """DEMO_MODE=true must return cache results without any network calls."""
    monkeypatch.setattr("services.search_orchestrator.DEMO_MODE", True)

    with (
        patch(
            "services.search_orchestrator._fetch_source", new_callable=AsyncMock
        ) as mock_fetch,
        patch(
            "services.serpapi_service.search_google_shopping_india",
            new_callable=AsyncMock,
        ) as mock_serp,
    ):
        results = await run_market_survey("S-band Software Defined Radio")

        assert results is not None
        assert len(results) == 1
        assert results[0]["is_demo_data"] is True
        mock_fetch.assert_not_called()
        mock_serp.assert_not_called()


@pytest.mark.asyncio
async def test_demo_mode_miss_returns_empty(monkeypatch):
    """DEMO_MODE=true with no cache entry must return [] (never the network)."""
    monkeypatch.setattr("services.search_orchestrator.DEMO_MODE", True)

    with (
        patch(
            "services.search_orchestrator._fetch_source", new_callable=AsyncMock
        ) as mock_fetch,
        patch(
            "services.serpapi_service.search_google_shopping_india",
            new_callable=AsyncMock,
        ) as mock_serp,
    ):
        results = await run_market_survey("quantum entangled toaster")

        assert results == []
        mock_fetch.assert_not_called()
        mock_serp.assert_not_called()


@pytest.mark.asyncio
async def test_live_mode_still_uses_demo_cache_fallback(monkeypatch):
    """Without DEMO_MODE, live fetches run first and demo cache is fallback."""
    monkeypatch.setattr("services.search_orchestrator.DEMO_MODE", False)

    with (
        patch(
            "services.search_orchestrator._fetch_source", new_callable=AsyncMock
        ) as mock_fetch,
        patch(
            "services.serpapi_service.search_google_shopping_india",
            new_callable=AsyncMock,
        ) as mock_serp,
    ):
        mock_fetch.return_value = {"error": "connection failed"}
        mock_serp.return_value = []

        results = await run_market_survey("S-band Software Defined Radio")

        assert results is not None
        assert len(results) == 1
        assert results[0]["is_demo_data"] is True
        mock_fetch.assert_called()
        mock_serp.assert_called()


@pytest.mark.asyncio
async def test_tier_3_runs_for_service_query(monkeypatch):
    """Service queries must now execute Tier 3 instead of skipping it."""
    monkeypatch.setattr("services.search_orchestrator.DEMO_MODE", True)

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
        mock_2.return_value = None
        mock_3.return_value = [
            {"tier": 3, "price": 2500.0, "source": "AMC Market", "is_demo_data": True}
        ]
        mock_4.return_value = None

        result = await get_price_benchmark(
            "Annual Maintenance Contract for Desktop Computers",
            query_mode="service",
        )

        assert result is not None
        assert result["resolved_tier"] == 3
        assert result["primary_result"]["price"] == 2500.0
        mock_3.assert_called_once()
