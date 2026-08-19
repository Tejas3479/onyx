"""Tier 0 & Tier 1 — Government Rate Lookups.

Tier 0: DGS&D rate contracts / ministry-notified fixed rates
Tier 1: GeM Business Analytics / GeM Last Purchase Price (demo-seeded)
"""

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy import delete, select

from database import GemLPPCache, NotifiedRate, async_session_maker

logger = logging.getLogger("onyx.gem_rate_lookup")

# Seed data paths
NOTIFIED_RATES_PATH = Path("data/notified_rates.json")
GEM_LPP_SEED_PATH = Path("data/gem_lpp_seed.json")

# Minimum fuzzy match score
MATCH_THRESHOLD = 65


async def seed_notified_rates() -> int:
    """Load notified rates from JSON seed file into the database."""
    if not NOTIFIED_RATES_PATH.exists():
        logger.warning("Notified rates seed file not found: %s", NOTIFIED_RATES_PATH)
        return 0

    with open(NOTIFIED_RATES_PATH, encoding="utf-8") as f:  # noqa: ASYNC230
        data = json.load(f)

    count = 0
    async with async_session_maker() as session:
        # Replace previous demo-seeded rows so the expanded dataset always loads
        await session.execute(
            delete(NotifiedRate).where(NotifiedRate.is_demo_data == True)
        )

        for item in data:
            record = NotifiedRate(
                item_category=item["item_category"],
                item_description=item["item_description"],
                rate=item["rate"],
                unit=item["unit"],
                authority=item["authority"],
                contract_number=item.get("contract_number"),
                valid_from=date.fromisoformat(item["valid_from"]),
                valid_until=date.fromisoformat(item["valid_until"])
                if item.get("valid_until")
                else None,
                is_active=True,
                is_demo_data=True,
            )
            session.add(record)
            count += 1
        await session.commit()

    logger.info("Seeded %d notified rates", count)
    return count


async def seed_gem_lpp() -> int:
    """Load GeM LPP cache from JSON seed file into the database."""
    if not GEM_LPP_SEED_PATH.exists():
        logger.warning("GeM LPP seed file not found: %s", GEM_LPP_SEED_PATH)
        return 0

    with open(GEM_LPP_SEED_PATH, encoding="utf-8") as f:  # noqa: ASYNC230
        data = json.load(f)

    count = 0
    async with async_session_maker() as session:
        # Replace previous demo-seeded rows so the expanded dataset always loads
        await session.execute(
            delete(GemLPPCache).where(GemLPPCache.is_demo_data == True)
        )

        for item in data:
            record = GemLPPCache(
                query_matched=item["query_matched"],
                product_name=item["product_name"],
                gem_product_id=item.get("gem_product_id"),
                catalog_price=item.get("catalog_price"),
                lpp_price=item.get("lpp_price"),
                source_label=item["source_label"],
                source_url=item.get("source_url"),
                seller_name=item.get("seller_name"),
                specifications=item.get("specifications", {}),
                is_demo_data=True,
            )
            session.add(record)
            count += 1
        await session.commit()

    logger.info("Seeded %d GeM LPP entries", count)
    return count


async def seed_all() -> dict[str, int]:
    """Seed all tier 0/1 data. Called at app startup."""
    nr = await seed_notified_rates()
    gem = await seed_gem_lpp()
    return {"notified_rates": nr, "gem_lpp": gem}


async def check_notified_rate(
    query: str,
    category: str | None = None,
) -> dict[str, Any] | None:
    """Tier 0: Check for DGS&D rate contracts / ministry-notified rates.

    Fuzzy-matches query against notified rate descriptions.
    Only returns active, non-expired rates.
    """
    async with async_session_maker() as session:
        stmt = select(NotifiedRate).where(NotifiedRate.is_active == True)
        if category:
            stmt = stmt.where(NotifiedRate.item_category == category)

        result = await session.execute(stmt)
        rates = result.scalars().all()

    if not rates:
        return None

    today = datetime.now(timezone.utc).date()
    best_match: NotifiedRate | None = None
    best_score: float = 0.0

    for rate in rates:
        # Skip expired rates
        if rate.valid_until and rate.valid_until < today:
            continue

        score = fuzz.token_set_ratio(query.lower(), rate.item_description.lower())
        if score > best_score:
            best_score = score
            best_match = rate

    if best_match is None or best_score < MATCH_THRESHOLD:
        return None

    return {
        "source_name": f"Notified Rate ({best_match.authority})",
        "price": best_match.rate,
        "currency": best_match.currency,
        "evidence_url": None,
        "evidence_reference": (
            best_match.contract_number or "Notified rate contract"
        ),
        "rationale": (
            f"DGS&D/Ministry notified rate for '{best_match.item_description}'. "
            f"Contract: {best_match.contract_number or 'N/A'}. "
            f"Valid: {best_match.valid_from.isoformat()} to "
            f"{best_match.valid_until.isoformat() if best_match.valid_until else 'ongoing'}. "
            f"Unit: {best_match.unit}. Match score: {best_score:.0f}%."
        ),
        "is_demo_data": best_match.is_demo_data,
        "confidence": "HIGH" if best_score >= 80 else "MEDIUM",
        "reliability": "HIGH",  # Government-notified rates are authoritative
    }


async def check_gem_business_analytics(
    query: str,
    specs: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Tier 1: Check GeM catalog prices / Last Purchase Price.

    Fuzzy-matches query against GeM LPP cache entries.
    Prefers LPP over catalog price when available.
    """
    async with async_session_maker() as session:
        stmt = select(GemLPPCache)
        result = await session.execute(stmt)
        entries = result.scalars().all()

    if not entries:
        return None

    best_match: GemLPPCache | None = None
    best_score: float = 0.0

    for entry in entries:
        score = fuzz.token_set_ratio(query.lower(), entry.query_matched.lower())

        # Boost for product name match
        name_score = fuzz.token_set_ratio(query.lower(), entry.product_name.lower())
        score = max(score, name_score)

        # Boost for spec overlap
        if specs and entry.specifications:
            overlap = len(set(specs.keys()) & set(entry.specifications.keys()))
            score = min(100, score + overlap * 3)

        if score > best_score:
            best_score = score
            best_match = entry

    if best_match is None or best_score < MATCH_THRESHOLD:
        return None

    # Prefer LPP over catalog price
    price = best_match.lpp_price or best_match.catalog_price
    price_type = "Last Purchase Price" if best_match.lpp_price else "Catalog Price"

    return {
        "source_name": f"GeM {price_type}",
        "price": price,
        "currency": "INR",
        "evidence_url": best_match.source_url,
        "rationale": (
            f"GeM {price_type} for '{best_match.product_name}'. "
            f"Product ID: {best_match.gem_product_id or 'N/A'}. "
            f"Seller: {best_match.seller_name or 'N/A'}. "
            f"Match score: {best_score:.0f}%."
        ),
        "is_demo_data": best_match.is_demo_data,
        "confidence": "HIGH" if best_score >= 80 else "MEDIUM",
        "reliability": "HIGH",  # GeM is government-authoritative
    }
