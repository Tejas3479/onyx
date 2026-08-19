"""Onyx Search API — cross-source product search across the price registry."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from rapidfuzz import fuzz
from sqlalchemy import select

from database import (
    DepartmentPurchaseRecord,
    GemLPPCache,
    NotifiedRate,
    async_session_maker,
)
from routers.auth_routes import require_current_user

logger = logging.getLogger("onyx.search")

router = APIRouter(prefix="/api/v1", tags=["search"])


def _score(query: str, candidate: str) -> int:
    if not candidate:
        return 0
    q = query.lower().strip()
    c = candidate.lower().strip()
    return int(
        max(
            fuzz.ratio(q, c),
            fuzz.token_set_ratio(q, c),
            fuzz.partial_ratio(q, c),
            # Substring containment — "cisco" should match "Cisco Catalyst 9300"
            95 if q in c else 0,
            85 if any(tok in c for tok in q.split() if len(tok) >= 3) else 0,
        )
    )


@router.get("/search")
async def search_registry(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(10, ge=1, le=25),
    user=Depends(require_current_user),
):
    """Search the Onyx price registry across all statutory tiers.

    Returns best fuzzy matches from Tier 0 (notified rates), Tier 1 (GeM LPP),
    and Tier 2 (department purchase records), so officers can locate an item
    and jump straight to a benchmark or report.
    """
    async with async_session_maker() as session:
        stmt = select(NotifiedRate).where(NotifiedRate.is_active == True)
        notified = (await session.execute(stmt)).scalars().all()
        gem = (await session.execute(select(GemLPPCache))).scalars().all()
        dept = (await session.execute(select(DepartmentPurchaseRecord))).scalars().all()

    scored: list[dict[str, Any]] = []

    for rate in notified:
        s = _score(q, rate.item_description)
        if s >= 55:
            scored.append(
                {
                    "match": rate.item_description,
                    "score": s,
                    "tier": 0,
                    "tier_label": "Notified Rate",
                    "source": f"Notified Rate ({rate.authority})",
                    "price": rate.rate,
                    "unit": rate.unit,
                    "currency": rate.currency,
                    "is_demo_data": rate.is_demo_data,
                }
            )

    for entry in gem:
        s = max(_score(q, entry.product_name), _score(q, entry.query_matched))
        if s >= 55:
            scored.append(
                {
                    "match": entry.product_name,
                    "score": s,
                    "tier": 1,
                    "tier_label": "GeM Business Analytics",
                    "source": entry.source_label,
                    "price": entry.lpp_price or entry.catalog_price,
                    "unit": "per unit",
                    "currency": "INR",
                    "is_demo_data": entry.is_demo_data,
                }
            )

    for record in dept:
        s = _score(q, record.item_description)
        if s >= 55:
            scored.append(
                {
                    "match": record.item_description,
                    "score": s,
                    "tier": 2,
                    "tier_label": "Department LPP",
                    "source": record.department,
                    "price": record.unit_price,
                    "unit": "per unit",
                    "currency": "INR",
                    "is_demo_data": False,
                }
            )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"query": q, "total": len(scored), "results": scored[:limit]}
