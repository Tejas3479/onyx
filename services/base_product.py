"""Canonical Base-Product identity resolution (Q1/Q8).

Different surface names for the same product — "Cisco Catalyst 9300-48P-A",
"Cisco 9300 Switch 48 Port", "cisco catalyst 9300" — are collapsed onto a
single canonical identity so price reasonability and LPP compliance clusters
stay coherent across naming variants and across departments.
"""

from rapidfuzz import fuzz
from sqlalchemy import select

from database import DepartmentPurchaseRecord, async_session_maker
from services.department_lpp import normalize_item_key

MATCH_THRESHOLD = 72.0


def canonicalize_product_name(name: str) -> str:
    """Normalize any item name to its canonical key."""
    return normalize_item_key(name)


async def resolve_base_product(
    query: str, department: str | None = None
) -> dict:
    """Match a benchmark query against prior department purchase records.

    Records are scoped to the requesting officer's department (RLS-lite), so
    no cross-department price leaks through the identity layer. Returns the
    canonical product identity plus the prior-price story when matched.
    """
    key = canonicalize_product_name(query)

    async with async_session_maker() as session:
        stmt = select(DepartmentPurchaseRecord)
        if department:
            stmt = stmt.where(DepartmentPurchaseRecord.department == department)
        records = (await session.execute(stmt)).scalars().all()

    scored: list[tuple[float, DepartmentPurchaseRecord]] = []
    for rec in records:
        rec_key = normalize_item_key(rec.item_description)
        score = fuzz.token_set_ratio(key, rec_key)
        if score >= MATCH_THRESHOLD:
            scored.append((score, rec))

    if not scored:
        return {
            "canonical_name": (query or "").strip(),
            "canonical_key": key,
            "match_score": None,
            "prior_records": 0,
            "prior_median_price": None,
            "prior_min": None,
            "prior_max": None,
            "prior_departments": [],
        }

    scored.sort(key=lambda t: -t[0])
    best_score, best = scored[0]
    prices = sorted(r[1].unit_price for r in scored)
    n = len(prices)
    median = (
        prices[n // 2]
        if n % 2
        else (prices[n // 2 - 1] + prices[n // 2]) / 2
    )
    depts = sorted(
        {r[1].department for r in scored if r[1].department}
    )

    return {
        "canonical_name": (best.item_description or query or "").strip(),
        "canonical_key": key,
        "match_score": round(best_score, 1),
        "prior_records": n,
        "prior_median_price": round(median, 2),
        "prior_min": prices[0],
        "prior_max": prices[-1],
        "prior_departments": depts,
    }


def count_base_products(records: list[dict]) -> int:
    """Distinct canonical identities present in a set of LPP records."""
    return len({normalize_item_key(r.get("item_description", "")) for r in records})