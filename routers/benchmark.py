"""Onyx Benchmark API — main entry point for price benchmarking."""

import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models import BenchmarkQuery, BenchmarkResponse, TierResult
from services.tier_waterfall import get_price_benchmark

logger = logging.getLogger("onyx.benchmark")

router = APIRouter(prefix="/api/v1", tags=["benchmark"])


@router.post("/benchmark", response_model=BenchmarkResponse)
async def run_benchmark(query: BenchmarkQuery):
    """
    Execute a GFR Rule 149(vii) tier waterfall price benchmark.

    Checks price sources in legally prescribed order:
    Tier 0 → Tier 1 → Tier 2 → Tier 3 → Tier 4
    """
    logger.info(
        "Benchmark request: product=%s, mode=%s, dept=%s",
        query.product_name,
        query.query_mode,
        query.department,
    )

    try:
        result = await get_price_benchmark(
            query=query.product_name,
            specs=query.specs,
            department=query.department,
            category=query.category,
            query_mode=query.query_mode,
            quantity=query.quantity,
        )
    except Exception as e:
        logger.exception("Benchmark failed")
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {e!s}")

    # Convert raw dicts to TierResult models
    primary = result["primary_result"]
    primary_tier_result = TierResult(
        tier=result["resolved_tier"],
        tier_label=result["tier_label"],
        source_name=primary.get("source_name", "Unknown"),
        price=primary.get("price"),
        price_range_low=primary.get("price_range_low"),
        price_range_high=primary.get("price_range_high"),
        currency=primary.get("currency", "INR"),
        confidence=primary.get("confidence", "LOW"),
        reliability=primary.get("reliability", "MEDIUM"),
        evidence_url=primary.get("evidence_url"),
        rationale=primary.get("rationale", ""),
        is_demo_data=primary.get("is_demo_data", False),
    )

    all_tier_results = []
    for r in result["all_results"]:
        all_tier_results.append(
            TierResult(
                tier=r.get("tier", 0),
                tier_label=r.get("tier_label", ""),
                source_name=r.get("source_name", "Unknown"),
                price=r.get("price"),
                price_range_low=r.get("price_range_low"),
                price_range_high=r.get("price_range_high"),
                currency=r.get("currency", "INR"),
                confidence=r.get("confidence", "LOW"),
                reliability=r.get("reliability", "MEDIUM"),
                evidence_url=r.get("evidence_url"),
                rationale=r.get("rationale", ""),
                is_demo_data=r.get("is_demo_data", False),
            )
        )

    search_id = str(uuid.uuid4())

    return BenchmarkResponse(
        search_id=search_id,
        query=query.product_name,
        query_mode=query.query_mode,
        status="completed",
        resolved_tier=result["resolved_tier"],
        tier_label=result["tier_label"],
        primary_result=primary_tier_result,
        all_results=all_tier_results,
        tier_trace=result["tier_trace"],
        statistics=result["statistics"],
        sources_checked=len(result["tier_trace"]),
        results_found=len(result["all_results"]),
    )


class NonStandardEstimateRequest(BaseModel):
    """Standalone request for Tier 4 estimation."""
    product_name: str
    specs: dict | None = None
    category: str | None = None


@router.post("/estimate/non-standard")
async def estimate_non_standard(req: NonStandardEstimateRequest):
    """Standalone Tier 4 endpoint — estimate price for non-standard items."""
    from services.tier_waterfall import _run_tier_4

    result = await _run_tier_4(req.product_name, req.specs)
    if result is None:
        return {
            "method_used": "insufficient_data",
            "estimated_price": None,
            "confidence_rationale": (
                "Insufficient data. Recommend referral to Local Purchase "
                "Committee for negotiated pricing per GFR."
            ),
        }
    return result
