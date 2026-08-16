"""Tier 4 — Non-Standard Item Estimator.

Handles items with no direct market listing (waveguides, antennae,
HF/VHF equipment, software defined radios, etc.) using:
  1. Spec-similarity search against known items
  2. Price-per-spec-unit extrapolation
  3. AliExpress international pricing (import cost basis)
  4. Insufficient data / committee referral
"""

import asyncio
import logging
from typing import Any

from rapidfuzz import fuzz

logger = logging.getLogger("onyx.non_standard_estimator")

# Minimum similarity score to consider items comparable
SIMILARITY_THRESHOLD = 55

# Known spec units and their typical price multipliers
# Used for price-per-spec-unit extrapolation
SPEC_UNITS: dict[str, dict[str, Any]] = {
    "frequency_ghz": {
        "unit": "GHz",
        "description": "Operating frequency",
        "typical_cost_factor": 1.15,  # 15% more per GHz step
    },
    "power_watts": {
        "unit": "W",
        "description": "Output power",
        "typical_cost_factor": 1.08,  # 8% more per watt step
    },
    "bandwidth_mhz": {
        "unit": "MHz",
        "description": "Bandwidth",
        "typical_cost_factor": 1.05,
    },
    "channels": {
        "unit": "ch",
        "description": "Number of channels",
        "typical_cost_factor": 1.10,
    },
    "ports": {
        "unit": "ports",
        "description": "Number of ports",
        "typical_cost_factor": 1.06,
    },
}


async def estimate_non_standard_item(
    query: str,
    specs: dict[str, Any] | None = None,
    category: str | None = None,
) -> dict[str, Any] | None:
    """Estimate price for a non-standard item.

    Tries three strategies in order:
      1. Spec-similarity match against known items
      2. Price-per-spec-unit extrapolation from partial data
      3. AliExpress international search for import cost basis

    Returns None only if all strategies fail AND there's no
    meaningful data to report (extremely rare — usually returns
    an "insufficient_data" result with committee recommendation).
    """
    logger.info("Tier 4 estimation for: %s (category: %s)", query, category)

    # Strategy 1: Gemini Search Grounding (Statutory AI Estimator)
    try:
        from services.gemini_grounding import estimate_non_standard_price_with_gemini

        gemini_est = await estimate_non_standard_price_with_gemini(query, specs)
        if gemini_est:
            return gemini_est
    except Exception as e:
        logger.warning("Gemini Grounding check failed: %s", e)

    # Strategy 2: Spec-similarity search against historical POs
    similar = await _find_similar_items(query, specs)
    if similar:
        estimated = _extrapolate_from_similar(query, specs, similar)
        if estimated:
            return estimated

    # Strategy 3: International marketplace search for import landed cost (1.42x)
    intl_result = await _check_international_sources(query)
    if intl_result:
        return intl_result

    # Strategy 4: Insufficient data — committee referral (Rule 155 LPC / Rule 166 PAC)
    return _insufficient_data_result(query, category)


async def _find_similar_items(
    query: str,
    specs: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Search for spec-similar items in department records and demo cache."""
    from sqlalchemy import select

    from database import DepartmentPurchaseRecord, async_session_maker

    similar_items: list[dict[str, Any]] = []

    # Search department purchase records
    try:
        async with async_session_maker() as session:
            stmt = select(DepartmentPurchaseRecord).limit(500)
            result = await session.execute(stmt)
            records = result.scalars().all()

        for record in records:
            # Fuzzy match on item description
            score = fuzz.token_set_ratio(query.lower(), record.item_description.lower())

            # Boost score if specs overlap
            if specs and record.specs:
                spec_keys_overlap = len(set(specs.keys()) & set(record.specs.keys()))
                score = min(100, score + spec_keys_overlap * 5)

            if score >= SIMILARITY_THRESHOLD:
                similar_items.append(
                    {
                        "item_description": record.item_description,
                        "unit_price": record.unit_price,
                        "specs": record.specs,
                        "match_score": score / 100.0,
                        "source": f"Dept Record ({record.department})",
                        "purchase_date": record.purchase_date.isoformat(),
                    }
                )
    except Exception as e:
        logger.warning("Failed to search department records: %s", e)

    # Also search demo cache for similar items
    try:
        from services.search_orchestrator import _load_demo_cache

        cache = _load_demo_cache()
        for cache_key, cache_results in cache.items():
            key_score = fuzz.token_set_ratio(query.lower(), cache_key)
            if key_score >= SIMILARITY_THRESHOLD:
                for cr in cache_results:
                    if cr.get("price") is not None:
                        similar_items.append(
                            {
                                "item_description": cr.get("product_name", cache_key),
                                "unit_price": cr["price"],
                                "specs": {},
                                "match_score": key_score / 100.0,
                                "source": cr.get("source_name", "Cache"),
                                "purchase_date": None,
                            }
                        )
    except Exception as e:
        logger.warning("Failed to search demo cache: %s", e)

    # Sort by match score descending
    similar_items.sort(key=lambda x: x["match_score"], reverse=True)
    return similar_items[:10]  # Return top 10


def _extrapolate_from_similar(
    query: str,
    specs: dict[str, Any] | None,
    similar_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Extrapolate price from similar items using spec-based adjustment."""
    if not similar_items:
        return None

    prices = [item["unit_price"] for item in similar_items]
    scores = [item["match_score"] for item in similar_items]

    # Weighted average: higher match score = higher weight
    total_weight = sum(scores)
    if total_weight == 0:
        return None

    weighted_price = sum(p * s for p, s in zip(prices, scores)) / total_weight

    # Calculate price range based on spread
    price_min = min(prices)
    price_max = max(prices)

    # Adjust range if specs suggest different capability level
    adjustment_factor = 1.0
    if specs:
        for spec_key in specs:
            if spec_key in SPEC_UNITS:
                try:
                    # If user's spec value is higher, adjust price up
                    factor = SPEC_UNITS[spec_key]["typical_cost_factor"]
                    adjustment_factor *= factor
                except (KeyError, TypeError):
                    pass

    estimated_price = round(weighted_price * adjustment_factor, 2)
    range_low = round(price_min * 0.85, 2)  # 15% below lowest similar
    range_high = round(price_max * 1.25, 2)  # 25% above highest similar

    # Build comparable items summary
    comparable = [
        {
            "item": item["item_description"],
            "price": item["unit_price"],
            "match_score": round(item["match_score"], 2),
            "source": item["source"],
        }
        for item in similar_items[:5]
    ]

    avg_score = sum(scores) / len(scores)
    method = "spec_similarity"
    confidence_rationale = (
        f"Estimated from {len(similar_items)} similar item(s) with "
        f"avg match score {avg_score:.0%}. "
        f"Weighted average: \u20b9{weighted_price:,.2f}"
    )
    if adjustment_factor != 1.0:
        confidence_rationale += (
            f", adjusted by {adjustment_factor:.2f}x for spec differences"
        )
    confidence_rationale += (
        f". Range: \u20b9{range_low:,.2f} \u2013 \u20b9{range_high:,.2f}. "
        "Recommend verification by technical committee."
    )

    return {
        "source_name": "Non-Standard Estimate (Spec Similarity)",
        "price": estimated_price,
        "price_range_low": range_low,
        "price_range_high": range_high,
        "currency": "INR",
        "evidence_url": None,
        "rationale": confidence_rationale,
        "is_demo_data": False,
        "confidence": "MEDIUM" if avg_score >= 0.7 else "LOW",
        "reliability": "MEDIUM" if len(similar_items) >= 3 else "LOW",
        "method_used": method,
        "comparable_items": comparable,
        "spec_match_score": round(avg_score, 2),
    }


async def _check_international_sources(query: str) -> dict[str, Any] | None:
    """Check AliExpress for international pricing as import cost basis."""
    from services.source_registry import get_sources_for_tier

    sources = get_sources_for_tier(4)
    if not sources:
        return None

    try:
        from services.price_extractor import extract_prices_from_content
        from services.search_orchestrator import _fetch_source

        # Fetch AliExpress
        source = sources[0]  # AliExpress
        fetch_result = await asyncio.wait_for(
            _fetch_source(source, query),
            timeout=20,
        )

        if fetch_result.get("error") or not fetch_result.get("content"):
            return None

        extracted = extract_prices_from_content(
            content=fetch_result["content"],
            source_name="AliExpress (Import Basis)",
            source_url=fetch_result["url"],
        )

        if not extracted:
            return None

        # Use median of extracted prices, add import duty estimate (28% GST + 10% customs)
        prices = [e["price"] for e in extracted if e.get("price") is not None]
        if not prices:
            return None

        median_intl = sorted(prices)[len(prices) // 2]
        import_factor = 1.42  # ~28% GST + ~10% customs + ~4% handling
        estimated_landed = round(median_intl * import_factor, 2)

        return {
            "source_name": "Non-Standard Estimate (Import Cost Basis)",
            "price": estimated_landed,
            "price_range_low": round(median_intl * 1.30, 2),
            "price_range_high": round(median_intl * 1.55, 2),
            "currency": "INR",
            "evidence_url": fetch_result.get("url"),
            "rationale": (
                f"Based on international pricing from AliExpress. "
                f"Median international price: \u20b9{median_intl:,.2f}. "
                f"Estimated landed cost (incl. 28%% GST + 10%% customs): "
                f"\u20b9{estimated_landed:,.2f}. "
                f"Range accounts for duty variation. "
                f"Recommend verification with authorized Indian distributors."
            ),
            "is_demo_data": False,
            "confidence": "LOW",
            "reliability": "LOW",
            "method_used": "import_cost_basis",
            "comparable_items": [
                {"item": e.get("product_name", "Unknown"), "price": e["price"]}
                for e in extracted[:3]
            ],
            "spec_match_score": None,
        }

    except Exception as e:
        logger.warning("International source check failed: %s", e)
        return None


def _insufficient_data_result(query: str, category: str | None) -> dict[str, Any]:
    """Return an insufficient data result with committee recommendation."""
    cat_note = f" in category '{category}'" if category else ""
    return {
        "source_name": "Manual Review Required",
        "price": None,
        "price_range_low": None,
        "price_range_high": None,
        "currency": "INR",
        "evidence_url": None,
        "rationale": (
            f"Insufficient pricing data found for '{query}'{cat_note} across "
            f"all automated sources (Tiers 0\u20133 and international markets). "
            f"This item appears to be a non-standard/specialized procurement. "
            f"Recommended actions:\n"
            f"1. Refer to Local Purchase Committee (LPC) for negotiated pricing per GFR Rule 155\n"
            f"2. Obtain quotations from at least 3 OEMs/authorized distributors\n"
            f"3. Consider Proprietary Article Certificate (PAC) per GFR Rule 166 if single-source justified"
        ),
        "is_demo_data": False,
        "confidence": "LOW",
        "reliability": "LOW",
        "method_used": "insufficient_data",
        "comparable_items": [],
        "spec_match_score": None,
    }
