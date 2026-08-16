"""Market Survey Orchestrator (Tier 3).

Parallel-fetches multiple e-commerce and government sources, extracts
prices from the scraped content, and returns aggregated results.

Uses the Crawlix fetch_engine under the hood, with demo cache fallback
for resilience during live demonstrations.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from services.price_extractor import (
    extract_prices_from_content,
    score_price_reliability,
)
from services.source_registry import get_enabled_market_sources

logger = logging.getLogger("onyx.search_orchestrator")

# Demo cache location
DEMO_CACHE_PATH = Path(os.getenv("DEMO_CACHE_PATH", "data/demo_cache.json"))

# Fetch timeout per source (seconds)
FETCH_TIMEOUT = 15


def _load_demo_cache() -> dict[str, Any]:
    """Load pre-populated demo results from disk."""
    if DEMO_CACHE_PATH.exists():
        try:
            with open(DEMO_CACHE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load demo cache: %s", e)
    return {}


async def _fetch_source(source: dict[str, Any], query: str) -> dict[str, Any]:
    """Fetch a single source URL and return raw content."""
    url = source["url_template"].format(query=quote_plus(query))
    source_name = source["name"]

    try:
        # Import fetch engine and playwright manager at runtime
        # to avoid circular imports during module loading
        from services.browser_manager import playwright_mgr
        from services.fetch_engine import run_fetch

        result = await asyncio.wait_for(
            run_fetch(
                url=url,
                method="GET",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                cookies={},
                body=None,
                json_body=None,
                session=None,
                render_js=source.get("render_js", False),
                scroll=False,
                proxy_url=None,
                max_retries=1,
                timeout=FETCH_TIMEOUT,
                impersonate="chrome",
                playwright_mgr=playwright_mgr,
                output_format="markdown",
                strip_links=True,
                llm_api_key=None,
                llm_provider="openai",
                json_schema=None,
                stealth=source.get("requires_stealth", False),
            ),
            timeout=FETCH_TIMEOUT + 5,
        )

        if result.get("error"):
            logger.warning(
                "Fetch error from %s: %s",
                source_name,
                result.get("error_message", "unknown"),
            )
            return {
                "source": source_name,
                "url": url,
                "content": None,
                "error": result["error"],
            }

        content = result.get("content", "")
        logger.info("Fetched %d chars from %s", len(content), source_name)
        return {"source": source_name, "url": url, "content": content, "error": None}

    except TimeoutError:
        logger.warning("Timeout fetching %s", source_name)
        return {"source": source_name, "url": url, "content": None, "error": "timeout"}
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", source_name, e)
        return {"source": source_name, "url": url, "content": None, "error": str(e)}


async def run_market_survey(
    query: str, specs: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Run a parallel market survey across all enabled Tier 3 sources.

    1. Fetches all sources in parallel
    2. Extracts prices from each source's content
    3. Scores reliability across all found prices
    4. Falls back to demo cache if all live fetches fail

    Returns a list of price result dicts ready for the tier waterfall.
    """
    sources = get_enabled_market_sources()
    if not sources:
        logger.warning("No market sources enabled")
        return []

    logger.info(
        "Starting market survey for '%s' across %d sources", query, len(sources)
    )

    # ── Parallel fetch across standard sources + SerpAPI ──
    from services.serpapi_service import search_google_shopping_india

    fetch_tasks = [_fetch_source(source, query) for source in sources]
    serp_task = search_google_shopping_india(query)

    fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
    serp_results = await serp_task

    # ── Extract prices from each successful fetch ──
    all_results: list[dict[str, Any]] = []

    # Add SerpAPI results if found
    if serp_results:
        all_results.extend(serp_results)

    for fetch_result in fetch_results:
        if not isinstance(fetch_result, dict):
            logger.warning("Fetch task exception: %s", fetch_result)
            continue

        if fetch_result.get("error") or not fetch_result.get("content"):
            continue

        # Extract prices from scraped content
        extracted = extract_prices_from_content(
            content=fetch_result["content"],
            source_name=fetch_result["source"],
            source_url=fetch_result["url"],
        )
        all_results.extend(extracted)

    # ── Demo cache fallback ──
    if not all_results:
        logger.info("No live results for '%s', checking demo cache", query)
        cached = _check_demo_cache(query)
        if cached:
            logger.info("Using %d cached results for '%s'", len(cached), query)
            return cached

    # ── Cross-source reliability scoring ──
    all_prices = [r["price"] for r in all_results if r.get("price") is not None]
    for result in all_results:
        if result.get("price") is not None:
            result["reliability"] = score_price_reliability(
                price=result["price"],
                all_prices=all_prices,
                source_name=result["source_name"],
            )

    logger.info(
        "Market survey for '%s': %d results from %d sources, %d prices found",
        query,
        len(all_results),
        len(sources),
        len(all_prices),
    )

    return all_results


def _check_demo_cache(query: str) -> list[dict[str, Any]] | None:
    """Check demo cache for pre-populated results.

    Matches query against cache keys using case-insensitive prefix matching.
    """
    cache = _load_demo_cache()
    if not cache:
        return None

    query_lower = query.lower().strip()

    # Exact match first
    if query_lower in cache:
        return cache[query_lower]

    # Prefix match
    for key, results in cache.items():
        if query_lower.startswith(key) or key.startswith(query_lower):
            return results

    return None
