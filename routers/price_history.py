"""Onyx Price History API — recent benchmark runs and their resolved prices."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select

from database import PriceResult, PriceSearch, User, async_session_maker
from routers.auth_routes import require_current_user

logger = logging.getLogger("onyx.price_history")

router = APIRouter(prefix="/api/v1", tags=["price-history"])


@router.get("/price-history")
async def list_price_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str | None = Query(None, description="Filter to a specific officer's runs"),
    user=Depends(require_current_user),
):
    """List recent benchmark runs with their resolved tier and primary price.

    Row-level isolation: non-admin officers only see runs from their own
    department (joined through the run's owning user). Admins see all.
    """
    async with async_session_maker() as session:
        stmt = (
            select(PriceSearch)
            .order_by(desc(PriceSearch.completed_at).nulls_last())
            .offset(offset)
            .limit(limit)
        )
        if user is not None and getattr(user, "role", "user") != "admin":
            if user.department:
                stmt = stmt.join(User, PriceSearch.user_id == User.id).where(
                    User.department == user.department
                )
            else:
                stmt = stmt.where(PriceSearch.user_id == user.id)
        if user_id:
            stmt = stmt.where(PriceSearch.user_id == user_id)
        searches = (await session.execute(stmt)).scalars().all()

        history = []
        for search in searches:
            result_stmt = (
                select(PriceResult)
                .where(PriceResult.search_id == search.id)
                .order_by(desc(PriceResult.extracted_at))
                .limit(5)
            )
            results = (await session.execute(result_stmt)).scalars().all()

            primary = next((r for r in results if r.price is not None), None)
            stats = search.statistics if isinstance(search.statistics, dict) else {}
            threshold = (
                search.procurement_threshold
                if isinstance(search.procurement_threshold, dict)
                else None
            )
            history.append(
                {
                    "search_id": search.id,
                    "user_id": search.user_id,
                    "query": search.query,
                    "query_mode": search.query_mode,
                    "resolved_tier": search.resolved_tier,
                    "tier_label": search.tier_label,
                    "price": primary.price if primary else None,
                    "currency": primary.currency if primary else "INR",
                    "source_name": primary.source_name if primary else None,
                    "confidence": primary.confidence if primary else None,
                    "any_demo_data": search.any_demo_data,
                    "estimated_value": search.estimated_value,
                    "delivery_location": search.delivery_location,
                    "statistics": stats,
                    "procurement_threshold": threshold,
                    "created_at": search.completed_at.isoformat()
                    if search.completed_at
                    else search.created_at.isoformat(),
                }
            )

    return {"total": len(history), "items": history}


@router.get("/price-history/{search_id}")
async def get_price_history_detail(
    search_id: str,
    user=Depends(require_current_user),
):
    """Return full detail for a single benchmark run, including all tier results."""
    async with async_session_maker() as session:
        search = await session.get(PriceSearch, search_id)
        if not search:
            raise HTTPException(status_code=404, detail="Search ID not found")

        result_stmt = (
            select(PriceResult)
            .where(PriceResult.search_id == search_id)
            .order_by(desc(PriceResult.extracted_at))
        )
        results = (await session.execute(result_stmt)).scalars().all()

    return {
        "search_id": search.id,
        "query": search.query,
        "query_mode": search.query_mode,
        "resolved_tier": search.resolved_tier,
        "tier_label": search.tier_label,
        "tier_trace": search.tier_skip_reasons,
        "any_demo_data": search.any_demo_data,
        "estimated_value": search.estimated_value,
        "delivery_location": search.delivery_location,
        "quantity": search.quantity,
        "statistics": (
            search.statistics if isinstance(search.statistics, dict) else {}
        ),
        "procurement_threshold": (
            search.procurement_threshold
            if isinstance(search.procurement_threshold, dict)
            else None
        ),
        "specs": search.specs if isinstance(search.specs, dict) else None,
        "base_product": (
            search.base_product if isinstance(search.base_product, dict) else None
        ),
        "freight": search.freight if isinstance(search.freight, dict) else None,
        "created_at": search.completed_at.isoformat()
        if search.completed_at
        else search.created_at.isoformat(),
        "results": [
            {
                "source_name": r.source_name,
                "source_url": r.source_url,
                "price": r.price,
                "currency": r.currency,
                "confidence": r.confidence,
                "rationale": r.raw_content,
            }
            for r in results
        ],
    }
