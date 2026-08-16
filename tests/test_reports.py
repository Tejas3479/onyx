import pytest
from httpx import AsyncClient

from app import app
from database import PriceResult, PriceSearch, async_session_maker


@pytest.mark.asyncio
async def test_generate_report_not_found(mock_redis):
    from httpx import ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post(
            "/api/v1/reports/generate", json={"search_id": "nonexistent"}
        )
    assert response.status_code == 404
    assert response.json() == {"detail": "Search ID not found"}


@pytest.mark.asyncio
async def test_generate_report_success(mock_redis):
    # Insert mock data
    async with async_session_maker() as session:
        search = PriceSearch(
            id="test-search-123",
            user_id="test-user",
            query="Laptop",
            quantity=1,
            resolved_tier=3,
            tier_label="Market Survey",
            status="completed",
        )
        session.add(search)

        result = PriceResult(
            search_id="test-search-123",
            source_name="Amazon",
            source_url="https://amazon.com",
            price=1200.0,
            currency="INR",
            confidence=0.9,
        )
        session.add(result)
        await session.commit()

    # We won't actually mock weasyprint PDF generation here; if it fails, it will fall back to HTML.
    # The endpoint should return 200 OK.
    from httpx import ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post(
            "/api/v1/reports/generate", json={"search_id": "test-search-123"}
        )

    assert response.status_code == 200
    assert response.headers["content-type"] in [
        "application/pdf",
        "text/html; charset=utf-8",
    ]


@pytest.mark.asyncio
async def test_generate_from_query(mock_redis):
    # Since this hits the full waterfall, we should just test if it invokes the workflow.
    # It might hit limits or fail if we don't mock it, but typically it returns some HTML or PDF.
    # To keep the test fast and avoid external calls, we can patch `get_price_benchmark`.
    from unittest.mock import patch

    mock_benchmark = {
        "search_id": "test-search-999",
        "query": "Laptop",
        "resolved_tier": 3,
        "tier_label": "Market Survey",
        "primary_result": {"price": 1000},
        "all_results": [],
        "tier_trace": {},
        "statistics": {},
    }

    with patch("routers.reports.get_price_benchmark", return_value=mock_benchmark):
        from httpx import ASGITransport

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/reports/generate-from-query", json={"product_name": "Laptop"}
            )

        assert response.status_code == 200
        assert response.headers["content-type"] in [
            "application/pdf",
            "text/html; charset=utf-8",
        ]
