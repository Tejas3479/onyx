import os

import pytest
from httpx import AsyncClient

from app import app
from database import (
    BenchmarkAuditLog,
    DelegationRecord,
    PriceResult,
    PriceSearch,
    async_session_maker,
    init_db,
)


@pytest.fixture(autouse=True)
async def setup_db(mock_redis):
    await init_db()
    yield


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
async def test_generate_report_includes_compliance_story(mock_redis):
    """The certificate report must render the full compliance story persisted
    at run time: L1/band, procurement threshold, golden params, base product,
    freight/landed cost, delegation and audit trail."""
    from httpx import ASGITransport

    async with async_session_maker() as session:
        search = PriceSearch(
            id="compliance-search-1",
            user_id="test-user",
            query="Cisco Catalyst 9300-48P-A Switch",
            quantity=2,
            resolved_tier=3,
            tier_label="Market Survey",
            status="completed",
            estimated_value=576000.0,
            delivery_location="New Delhi",
            specs={"Ports": "48", "PoE": "Yes"},
            statistics={
                "min": 285000.0,
                "max": 288000.0,
                "avg": 286500.0,
                "median": 286500.0,
                "count": 4,
                "l1": 285000.0,
                "l1_source": "GeM Portal",
                "competitive_pool": 4,
                "band_low": 214875.0,
                "band_high": 358125.0,
                "within_band": True,
            },
            procurement_threshold={
                "mode": "Advertised / Open Competitive Bidding",
                "rule": "GFR 2017 Rule 163",
                "min_quotes": 3,
                "quotes_obtained": 4,
                "compliant": True,
                "reason": "4/3 independent quotes gathered",
            },
            base_product={
                "canonical_name": "Cisco Catalyst 9300-48P-A Switch",
                "match_score": 96.0,
                "prior_records": 1,
                "prior_median_price": 291000.0,
            },
            freight={
                "delivery_location": "New Delhi",
                "region_label": "Metro city (local road)",
                "freight_pct": 0.6,
                "goods_value": 576000.0,
                "freight_amount": 3456.0,
                "landed_total": 579456.0,
            },
        )
        session.add(search)
        session.add(
            PriceResult(
                search_id="compliance-search-1",
                source_name="GeM Portal",
                source_url="https://gem.gov.in",
                price=285000.0,
                confidence="HIGH",
            )
        )
        session.add(
            DelegationRecord(
                search_id="compliance-search-1",
                delegated_by_name="Shri R. K. Sharma",
                delegate_to_name="Col. R. Sharma",
                status="completed",
                decision="approved",
                decision_note="Price within band",
            )
        )
        session.add(
            BenchmarkAuditLog(
                search_id="compliance-search-1",
                action="benchmark_created",
                actor_name="Shri R. K. Sharma",
            )
        )
        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post(
            "/api/v1/reports/generate",
            json={"search_id": "compliance-search-1", "output_format": "html"},
        )

    assert response.status_code == 200
    body = response.text
    for needle in (
        "L1 Competitive Bid",
        "Reasonableness Band",
        "PRIMARY WITHIN BAND",
        "Procurement Threshold Compliance",
        "Open Competitive Bidding",
        "Golden Parameters",
        "Ports:",
        "Canonical Base-Product Identity",
        "Prior Median Price",
        "Landed Cost (Delivery Location)",
        "Landed Total",
        "Delegation &amp; Audit Trail",
        "Col. R. Sharma",
        "benchmark_created",
    ):
        assert needle in body, f"report missing: {needle}"


@pytest.mark.asyncio
async def test_pdf_certificate_renders_compliance_story(mock_redis):
    """The ReportLab fallback certificate (Windows, no WeasyPrint) must render
    the compliance story without crashing, so the downloaded PDF artifact is
    compliance-complete too."""
    from services.report_generator import save_report

    ctx = {
        "statistics": {
            "l1": 285000.0,
            "competitive_pool": 4,
            "band_low": 214875.0,
            "band_high": 358125.0,
            "within_band": True,
        },
        "procurement_threshold": {
            "mode": "Advertised / Open Competitive Bidding",
            "rule": "GFR 2017 Rule 163",
            "min_quotes": 3,
            "quotes_obtained": 4,
            "compliant": True,
            "guidance": "4 quotes exceed the 3 required.",
        },
        "specs": {"Ports": "48", "PoE": "Yes"},
        "base_product": {
            "canonical_name": "Cisco Catalyst 9300-48P-A Switch",
            "match_score": 96.0,
            "prior_records": 1,
            "prior_median_price": 291000.0,
        },
        "freight": {
            "delivery_location": "New Delhi",
            "region_label": "Metro city (local road)",
            "freight_pct": 0.6,
            "goods_value": 576000.0,
            "freight_amount": 3456.0,
            "landed_total": 579456.0,
        },
        "delegations": [
            {
                "delegate_to_name": "Col. R. Sharma",
                "delegated_by_name": "Shri R. K. Sharma",
                "status": "completed",
                "decision": "approved",
            }
        ],
        "audit_log": [
            {"action": "benchmark_created", "actor_name": "Shri R. K. Sharma"}
        ],
    }

    path = save_report(
        html_content="<html><body><h1>Test</h1></body></html>",
        search_id="pdf-compliance-1",
        fmt="pdf",
        query="Cisco Catalyst 9300-48P-A Switch",
        any_demo_data=True,
        pdf_context=ctx,
    )
    assert path.endswith(".pdf")
    assert os.path.exists(path)
    with open(path, "rb") as fh:
        assert b"%PDF" in fh.read(1024)


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
