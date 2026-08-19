"""Onyx Benchmark API — main entry point for price benchmarking."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database import (
    BenchmarkAuditLog,
    PriceResult,
    PriceSearch,
    async_session_maker,
)
from models import BenchmarkQuery, BenchmarkResponse, TierResult
from routers.auth_routes import require_current_user
from services.base_product import resolve_base_product
from services.freight_estimator import estimate_freight
from services.procurement_threshold import evaluate_procurement_threshold
from services.tier_waterfall import get_price_benchmark

logger = logging.getLogger("onyx.benchmark")

router = APIRouter(prefix="/api/v1", tags=["benchmark"])


def _evidence_url(result: dict) -> str | None:
    """Resolve the evidence link from either key used across services.

    Live market extraction (price_extractor, demo_cache) emits ``source_url``,
    while gem_rate_lookup / serpapi / gemini_grounding emit ``evidence_url``.
    """
    return result.get("evidence_url") or result.get("source_url")


def _count_sources_checked(result: dict) -> int:
    """Count distinct evidence sources actually consulted across the waterfall.

    Each priced result in ``all_results`` corresponds to one consulted source;
    Tier 3 market survey yields one entry per platform/listing, so we dedupe by
    source name + evidence link rather than counting tiers.
    """
    sources: set[tuple[str, str]] = set()
    for r in result["all_results"]:
        if r.get("price") is None:
            continue  # skipped / "manual review" rows consulted nothing
        url = _evidence_url(r) or ""
        sources.add((r.get("source_name", ""), url))
    return len(sources)


@router.post("/benchmark", response_model=BenchmarkResponse)
async def run_benchmark(query: BenchmarkQuery, user=Depends(require_current_user)):
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

    # Canonical base-product identity vs. this department's purchase history.
    try:
        base_product = await resolve_base_product(
            query.product_name, query.department
        )
    except Exception as e:
        logger.warning("Base-product resolution failed: %s", e)
        base_product = None

    # Demo-simulated freight / landed cost for the delivery location.
    # Computed after `primary` is defined below (it needs the primary price).
    freight = None

    # Convert raw dicts to TierResult models
    primary = result["primary_result"]
    if query.query_mode == "product" and query.delivery_location:
        freight = estimate_freight(
            location=query.delivery_location,
            unit_price=primary.get("price"),
            quantity=query.quantity,
        )
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
        evidence_url=_evidence_url(primary),
        evidence_reference=primary.get("evidence_reference"),
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
                evidence_url=_evidence_url(r),
                evidence_reference=r.get("evidence_reference"),
                rationale=r.get("rationale", ""),
                is_demo_data=r.get("is_demo_data", False),
            )
        )

    search_id = str(uuid.uuid4())

    try:
        async with async_session_maker() as session:
            search_record = PriceSearch(
                id=search_id,
                user_id=(user.id if user else "anonymous"),
                query=query.product_name,
                query_type=query.query_type,
                category=query.category,
                quantity=query.quantity,
                status="completed",
                completed_at=datetime.now(timezone.utc),
                sources_checked=_count_sources_checked(result),
                results_found=len(result["all_results"]),
                resolved_tier=result["resolved_tier"],
                tier_label=result["tier_label"],
                tier_skip_reasons=result["tier_trace"],
                query_mode=query.query_mode,
                service_type=query.service_type,
                service_duration=query.service_duration,
                service_scope=query.service_scope,
                service_location=query.service_location,
                any_demo_data=(
                    primary_tier_result.is_demo_data
                    or any(tr.is_demo_data for tr in all_tier_results)
                ),
                estimated_value=query.estimated_value,
                delivery_location=query.delivery_location,
                specs=query.specs or None,
                statistics=result.get("statistics"),
                procurement_threshold=(
                    evaluate_procurement_threshold(
                        value=query.estimated_value,
                        quotes_obtained=(result.get("statistics") or {}).get(
                            "competitive_pool", 0
                        ),
                        price_found=(primary.get("price") is not None),
                    )
                    if query.estimated_value is not None
                    else None
                ),
                base_product=base_product,
                freight=freight,
            )
            session.add(search_record)

            # Append-only audit trail entry for the run (Q15).
            session.add(
                BenchmarkAuditLog(
                    search_id=search_id,
                    action="benchmark_created",
                    actor_name=user.name if user else None,
                    note=f"Benchmark for '{query.product_name}' resolved at tier {result['tier_label']}",
                )
            )

            for tr in all_tier_results:
                pr = PriceResult(
                    search_id=search_id,
                    source_name=tr.source_name,
                    source_url=tr.evidence_url or "",
                    price=tr.price,
                    currency=tr.currency,
                    confidence=tr.confidence,
                    raw_content=tr.rationale,
                )
                session.add(pr)

            await session.commit()
    except Exception as e:
        logger.warning(f"Failed to persist benchmark search: {e}")

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
        sources_checked=_count_sources_checked(result),
        results_found=len(result["all_results"]),
        any_demo_data=(
            primary_tier_result.is_demo_data
            or any(tr.is_demo_data for tr in all_tier_results)
        ),
        procurement_threshold=evaluate_procurement_threshold(
            value=query.estimated_value,
            quotes_obtained=(result.get("statistics") or {}).get(
                "competitive_pool", 0
            ),
            price_found=(primary.get("price") is not None),
        ),
        specs=query.specs or None,
        base_product=base_product,
        freight=freight,
    )


class NonStandardEstimateRequest(BaseModel):
    """Standalone request for Tier 4 estimation."""

    product_name: str
    specs: dict | None = None
    category: str | None = None


@router.post("/estimate/non-standard")
async def estimate_non_standard(
    req: NonStandardEstimateRequest, user=Depends(require_current_user)
):
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
