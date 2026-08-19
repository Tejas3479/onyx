from unittest.mock import AsyncMock, patch

import pytest

from services.tier_waterfall import get_price_benchmark


@pytest.mark.asyncio
async def test_waterfall_resolves_tier_0():
    mock_tier_0 = {"tier": 0, "price": 1000, "source": "Notified Rate"}

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
        mock_1.return_value = {"tier": 1, "price": 1100, "source": "GeM BA"}
        mock_2.return_value = None
        mock_3.return_value = None
        mock_4.return_value = None

        result = await get_price_benchmark("laptop")

        assert result is not None
        assert result["resolved_tier"] == 0
        assert result["primary_result"] is not None
        assert result["primary_result"]["price"] == 1000
        mock_0.assert_called_once()
        # Even if Tier 0 matches, the waterfall collects supplementary evidence from lower tiers
        # We can just verify it correctly selected Tier 0 as the primary result.


@pytest.mark.asyncio
async def test_waterfall_falls_back_to_tier_3():
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
            {"tier": 3, "price": 1200, "source": "Amazon", "is_primary": True}
        ]
        mock_4.return_value = None

        result = await get_price_benchmark("laptop")

        assert result is not None
        assert result["resolved_tier"] == 3
        assert result["primary_result"] is not None
        assert result["primary_result"]["price"] == 1200
        mock_0.assert_called_once()
        mock_1.assert_called_once()
        mock_2.assert_called_once()
        mock_3.assert_called_once()


@pytest.mark.asyncio
async def test_waterfall_computes_l1_and_reasonableness_band():
    """Rule 149(vii): L1 (Lowest-1) of the competitive pool + ±25% median band."""
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
            {"price": 1200, "source_name": "Amazon India", "vendor_name": "V1"},
            {"price": 1000, "source_name": "Flipkart", "vendor_name": "V2"},
            {"price": 1300, "source_name": "IndiaMART", "vendor_name": "V3"},
            {"price": 2000, "source_name": "GeM Portal", "vendor_name": "V4"},
        ]
        mock_4.return_value = None

        result = await get_price_benchmark("laptop")

        stats = result["statistics"]
        assert stats["l1"] == 1000.0
        assert stats["l1_source"] == "Flipkart"
        assert stats["l1_vendor"] == "V2"
        assert stats["competitive_pool"] == 4
        assert stats["l1_valid"] is True
        assert stats["median"] == 1250.0
        assert stats["band_low"] == 937.5
        assert stats["band_high"] == 1562.5
        # Primary (results[0]) = 1200 sits inside the band
        assert stats["primary_price"] == 1200.0
        assert stats["within_band"] is True
        assert stats["reasonableness_gap_pct"] == -4.0


@pytest.mark.asyncio
async def test_waterfall_band_flags_outlier_primary():
    """A primary price far outside the ±25% band must be flagged."""
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
            {"price": 500000, "source_name": "GeM Portal", "vendor_name": "V1"},
            {"price": 1100000, "source_name": "Amazon India", "vendor_name": "V2"},
            {"price": 1200000, "source_name": "Flipkart", "vendor_name": "V3"},
            {"price": 1150000, "source_name": "IndiaMART", "vendor_name": "V4"},
        ]
        mock_4.return_value = None

        result = await get_price_benchmark("router")

        stats = result["statistics"]
        assert stats["l1"] == 500000.0
        assert stats["within_band"] is False
        assert stats["reasonableness_gap_pct"] == -55.6
