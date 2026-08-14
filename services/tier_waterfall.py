"""
GFR Rule 149(vii) Tier Waterfall Engine.

Checks price sources in the legally prescribed order of preference:
  Tier 0: Notified Rate (DGS&D / ministry rate contracts)
  Tier 1: GeM Business Analytics / GeM LPP + CPPP tender data
  Tier 2: Department's Own Last Purchase Price
  Tier 3: Market Survey (Amazon, IndiaMART, Flipkart, Google Shopping, GeM catalog)
  Tier 4: Non-Standard Item Estimator (spec-similarity / should-cost)

The waterfall short-circuits on the FIRST tier that returns a primary result,
but continues collecting supplementary evidence from lower tiers to populate
`all_results` for richer reports.
"""

import logging
from typing import Any

logger = logging.getLogger("onyx.tier_waterfall")

# Tier label constants
TIER_LABELS = {
    0: "Notified Rate",
    1: "GeM Business Analytics",
    2: "Department Last Purchase Price",
    3: "Market Survey",
    4: "Non-Standard Estimate",
}


async def _check_tier_0(category: str | None) -> dict | None:
    """Tier 0: Check DGS&D rate contracts / ministry-notified fixed rates."""
    # TODO: Phase 6 — implement via gem_rate_lookup.check_notified_rate()
    logger.debug("Tier 0: Checking notified rates for category=%s", category)
    return None


async def _check_tier_1(query: str, specs: dict | None) -> dict | None:
    """Tier 1: Check GeM Business Analytics / GeM LPP + CPPP."""
    # TODO: Phase 6 — implement via gem_rate_lookup.check_gem_business_analytics()
    logger.debug("Tier 1: Checking GeM BA/LPP for query=%s", query)
    return None


async def _check_tier_2(
    query: str, specs: dict | None, department: str | None
) -> dict | None:
    """Tier 2: Check department's own last purchase price."""
    # TODO: Phase 2 — implement via department_lpp.check_department_lpp()
    logger.debug("Tier 2: Checking department LPP for query=%s, dept=%s", query, department)
    return None


async def _run_tier_3(query: str, specs: dict | None) -> list[dict]:
    """Tier 3: Run market survey across multiple sources."""
    # TODO: Phase 3 — implement via search_orchestrator.run_market_survey()
    logger.debug("Tier 3: Running market survey for query=%s", query)
    return []


async def _run_tier_4(query: str, specs: dict | None) -> dict | None:
    """Tier 4: Non-standard item estimation."""
    # TODO: Phase 4 — implement via non_standard_estimator.estimate_non_standard_item()
    logger.debug("Tier 4: Running non-standard estimator for query=%s", query)
    return None


async def get_price_benchmark(
    query: str,
    specs: dict | None = None,
    department: str | None = None,
    category: str | None = None,
    query_mode: str = "product",
    quantity: int = 1,
) -> dict[str, Any]:
    """
    Execute the GFR Rule 149(vii) tier waterfall.

    Returns a dict with:
      - resolved_tier: int (0-4)
      - tier_label: str
      - primary_result: dict (the best result from the resolving tier)
      - all_results: list[dict] (results from all tiers that returned data)
      - tier_trace: dict (explanation of each tier's outcome)
      - statistics: dict (min/max/avg/median across all prices)
    """
    tier_trace: dict[str, str] = {}
    all_results: list[dict] = []
    primary_result: dict | None = None
    resolved_tier: int | None = None

    # ── Tier 0: Notified Rates ──
    result = await _check_tier_0(category)
    if result:
        if primary_result is None:
            primary_result = result
            resolved_tier = 0
        all_results.append({**result, "tier": 0, "tier_label": TIER_LABELS[0]})
        tier_trace["tier_0"] = f"Found: {result.get('source_name', 'notified rate')}"
    else:
        tier_trace["tier_0"] = "No DGS&D rate contract found for this category"

    # ── Tier 1: GeM BA / LPP ──
    result = await _check_tier_1(query, specs)
    if result:
        if primary_result is None:
            primary_result = result
            resolved_tier = 1
        all_results.append({**result, "tier": 1, "tier_label": TIER_LABELS[1]})
        tier_trace["tier_1"] = f"Found: {result.get('source_name', 'GeM')}"
    else:
        tier_trace["tier_1"] = "No GeM LPP/catalog match found"

    # ── Tier 2: Department LPP ──
    result = await _check_tier_2(query, specs, department)
    if result:
        if primary_result is None:
            primary_result = result
            resolved_tier = 2
        all_results.append({**result, "tier": 2, "tier_label": TIER_LABELS[2]})
        tier_trace["tier_2"] = f"Found: {result.get('source_name', 'department LPP')}"
    else:
        tier_trace["tier_2"] = "No department purchase history match"

    # ── Tier 3: Market Survey (skip for service queries) ──
    if query_mode == "product":
        results = await _run_tier_3(query, specs)
        if results:
            if primary_result is None:
                primary_result = results[0]
                resolved_tier = 3
            for r in results:
                all_results.append({**r, "tier": 3, "tier_label": TIER_LABELS[3]})
            tier_trace["tier_3"] = f"Found {len(results)} market result(s)"
        else:
            tier_trace["tier_3"] = "No market survey results found"
    else:
        tier_trace["tier_3"] = "Skipped: service query (no product catalog search)"

    # ── Tier 4: Non-Standard Estimator ──
    if primary_result is None:
        result = await _run_tier_4(query, specs)
        if result:
            primary_result = result
            resolved_tier = 4
            all_results.append({**result, "tier": 4, "tier_label": TIER_LABELS[4]})
            tier_trace["tier_4"] = f"Estimated via {result.get('method_used', 'heuristic')}"
        else:
            tier_trace["tier_4"] = "Insufficient data for estimation"
            # Final fallback — no tier resolved
            resolved_tier = 4
            primary_result = {
                "source_name": "Manual Review Required",
                "price": None,
                "rationale": (
                    "Insufficient data across all tiers. Recommend referral to "
                    "Local Purchase Committee for negotiated pricing per GFR."
                ),
                "method_used": "insufficient_data",
            }
            all_results.append({**primary_result, "tier": 4, "tier_label": TIER_LABELS[4]})
    else:
        tier_trace["tier_4"] = "Skipped: resolved at earlier tier"

    # ── Compute statistics across all priced results ──
    prices = [r["price"] for r in all_results if r.get("price") is not None]
    statistics: dict[str, Any] = {}
    if prices:
        prices_sorted = sorted(prices)
        n = len(prices_sorted)
        statistics = {
            "min": prices_sorted[0],
            "max": prices_sorted[-1],
            "avg": round(sum(prices_sorted) / n, 2),
            "median": round(
                prices_sorted[n // 2]
                if n % 2
                else (prices_sorted[n // 2 - 1] + prices_sorted[n // 2]) / 2,
                2,
            ),
            "count": n,
        }

    return {
        "resolved_tier": resolved_tier,
        "tier_label": TIER_LABELS.get(resolved_tier, "Unknown"),
        "primary_result": primary_result,
        "all_results": all_results,
        "tier_trace": tier_trace,
        "statistics": statistics,
    }
