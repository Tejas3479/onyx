"""Source registry for Onyx price benchmarking.

Each source has a tier label indicating which GFR tier it serves,
and configuration for the fetch engine (JS rendering, stealth mode, etc.).
"""

from typing import Any

# ── Tier 3: Market Survey Sources ──
TIER_3_SOURCES: list[dict[str, Any]] = [
    {
        "name": "GeM Portal",
        "url_template": "https://mkp.gem.gov.in/search?q={query}",
        "render_js": True,
        "requires_stealth": False,
        "enabled": True,
        "tier": 3,
        "tier_label": "Market Survey",
        "priority": 1,  # GeM catalog is the most authoritative market source
    },
    {
        "name": "Amazon India",
        "url_template": "https://www.amazon.in/s?k={query}",
        "render_js": True,
        "requires_stealth": True,
        "enabled": True,
        "tier": 3,
        "tier_label": "Market Survey",
        "priority": 2,
    },
    {
        "name": "IndiaMART",
        "url_template": "https://dir.indiamart.com/search.mp?ss={query}",
        "render_js": False,
        "requires_stealth": False,
        "enabled": True,
        "tier": 3,
        "tier_label": "Market Survey",
        "priority": 3,
    },
    {
        "name": "Flipkart",
        "url_template": "https://www.flipkart.com/search?q={query}",
        "render_js": True,
        "requires_stealth": True,
        "enabled": True,
        "tier": 3,
        "tier_label": "Market Survey",
        "priority": 4,
    },
    {
        "name": "Google Shopping",
        "url_template": "https://www.google.com/search?tbm=shop&q={query}",
        "render_js": True,
        "requires_stealth": True,
        "enabled": True,
        "tier": 3,
        "tier_label": "Market Survey",
        "priority": 5,
    },
]

# ── Tier 1: CPPP Tender Archives ──
TIER_1_SOURCES: list[dict[str, Any]] = [
    {
        "name": "CPPP Tenders",
        "url_template": "https://etenders.gov.in/eprocure/app?page=FrontEndLatestActiveTenders&service=page",
        "render_js": True,
        "requires_stealth": False,
        "enabled": False,  # Requires login; placeholder for future
        "tier": 1,
        "tier_label": "GeM Business Analytics",
        "priority": 1,
    },
]

# ── Tier 4: International / Non-Standard Sources ──
TIER_4_SOURCES: list[dict[str, Any]] = [
    {
        "name": "AliExpress",
        "url_template": "https://www.aliexpress.com/wholesale?SearchText={query}",
        "render_js": True,
        "requires_stealth": True,
        "enabled": True,
        "tier": 4,
        "tier_label": "Non-Standard Estimate",
        "priority": 1,
    },
]

# Combined flat list for backward compatibility
SOURCES = TIER_3_SOURCES + TIER_1_SOURCES + TIER_4_SOURCES


def get_sources_for_tier(tier: int) -> list[dict[str, Any]]:
    """Return enabled sources for a specific tier."""
    if tier == 1:
        return [s for s in TIER_1_SOURCES if s["enabled"]]
    if tier == 3:
        return [s for s in TIER_3_SOURCES if s["enabled"]]
    if tier == 4:
        return [s for s in TIER_4_SOURCES if s["enabled"]]
    return []


def get_enabled_market_sources() -> list[dict[str, Any]]:
    """Return all enabled Tier 3 market survey sources, sorted by priority."""
    return sorted(
        [s for s in TIER_3_SOURCES if s["enabled"]],
        key=lambda s: s["priority"],
    )
