from unittest.mock import AsyncMock, patch

import pytest

from services.tier_waterfall import resolve_price_waterfall


@pytest.mark.asyncio
async def test_waterfall_resolves_tier_0():
    mock_tier_0 = {"tier": 0, "price": 1000, "source": "Notified Rate"}
    
    with patch("services.tier_waterfall._check_tier_0", new_callable=AsyncMock) as mock_0, \
         patch("services.tier_waterfall._check_tier_1", new_callable=AsyncMock) as mock_1, \
         patch("services.tier_waterfall._check_tier_2", new_callable=AsyncMock), \
         patch("services.tier_waterfall._check_tier_3", new_callable=AsyncMock), \
         patch("services.tier_waterfall._check_tier_4", new_callable=AsyncMock):
        
        mock_0.return_value = mock_tier_0
        mock_1.return_value = {"tier": 1, "price": 1100, "source": "GeM BA"}
        
        result, _ = await resolve_price_waterfall("laptop", None, None)
        
        assert result is not None
        assert result["tier"] == 0
        assert result["price"] == 1000
        mock_0.assert_called_once()
        # Even if Tier 0 matches, the waterfall collects supplementary evidence from lower tiers
        # We can just verify it correctly selected Tier 0 as the primary result.

@pytest.mark.asyncio
async def test_waterfall_falls_back_to_tier_3():
    with patch("services.tier_waterfall._check_tier_0", new_callable=AsyncMock) as mock_0, \
         patch("services.tier_waterfall._check_tier_1", new_callable=AsyncMock) as mock_1, \
         patch("services.tier_waterfall._check_tier_2", new_callable=AsyncMock) as mock_2, \
         patch("services.tier_waterfall._check_tier_3", new_callable=AsyncMock) as mock_3, \
         patch("services.tier_waterfall._check_tier_4", new_callable=AsyncMock):
        
        mock_0.return_value = None
        mock_1.return_value = None
        mock_2.return_value = None
        mock_3.return_value = {"tier": 3, "price": 1200, "source": "Amazon", "is_primary": True}
        
        result, _all_res = await resolve_price_waterfall("laptop", None, None)
        
        assert result is not None
        assert result["tier"] == 3
        assert result["price"] == 1200
        mock_0.assert_called_once()
        mock_1.assert_called_once()
        mock_2.assert_called_once()
        mock_3.assert_called_once()
