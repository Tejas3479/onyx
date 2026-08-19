"""Demo-simulated location-aware freight / landed-cost estimation (Q10).

Live transport quotes are out of scope for the demo, so Onyx simulates a
transparent freight adder bucketed by delivery region — the estimate is always
flagged as a demo simulation and never passed off as a real freight quote.
"""

import re

METRO_KEYWORDS = (
    "delhi",
    "ncr",
    "mumbai",
    "kolkata",
    "chennai",
    "bengaluru",
    "bangalore",
    "hyderabad",
    "pune",
    "ahmedabad",
    "jaipur",
    "lucknow",
)

NORTH_EAST_KEYWORDS = (
    "assam",
    "meghalaya",
    "manipur",
    "tripura",
    "mizoram",
    "nagaland",
    "arunachal",
    "sikkim",
    "shillong",
    "guwahati",
    "imphal",
    "aizawl",
    "kohima",
    "itanagar",
    "gangtok",
)

ISLAND_KEYWORDS = (
    "andaman",
    "nicobar",
    "lakshadweep",
    "port blair",
)


def _region_for(location: str) -> tuple[str, float]:
    """Return (region_label, freight_pct) for a delivery location."""
    loc = (location or "").lower()
    if any(k in loc for k in ISLAND_KEYWORDS):
        return "Island Territory (sea freight)", 4.5
    if any(k in loc for k in NORTH_EAST_KEYWORDS):
        return "North-East (transit premium)", 2.2
    if any(k in loc for k in METRO_KEYWORDS):
        return "Metro city (local road)", 0.6
    return "Inter-state (road/rail)", 1.2


def estimate_freight(
    location: str | None,
    unit_price: float | None,
    quantity: int = 1,
) -> dict | None:
    """Estimate freight + landed cost for a delivery location.

    Returns None when no location or no benchmarked price is available.
    The result is always flagged ``is_demo_simulated=True``.
    """
    if not location or unit_price is None:
        return None

    region_label, pct = _region_for(location)
    freight_amount = round(unit_price * quantity * pct / 100.0, 2)
    landed_total = round(unit_price * quantity + freight_amount, 2)

    return {
        "delivery_location": location.strip(),
        "region_label": region_label,
        "freight_pct": pct,
        "freight_amount": freight_amount,
        "quantity": quantity,
        "goods_value": round(unit_price * quantity, 2),
        "landed_total": landed_total,
        "is_demo_simulated": True,
        "note": (
            f"Simulated freight estimate for {location.strip()} "
            f"({region_label.lower()}, {pct:g}% of goods value). For a live "
            "landed-cost quotation, obtain a transport rate from a registered "
            "carrier before award."
        ),
    }