"""SerpAPI Google Shopping India Price Discovery Service.

Fetches real-time commercial retail and B2B prices from Google Shopping India (gl=in).
Gracefully falls back if SERPAPI_KEY is not configured.
"""

import logging
import os
import re
import typing
import httpx

logger = logging.getLogger("onyx.serpapi")

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


async def search_google_shopping_india(
    query: str,
    max_results: int = 5,
    timeout_sec: float = 6.0,
) -> list[dict[str, typing.Any]]:
    """Search Google Shopping India via SerpAPI.

    Returns a list of structured price result dicts compatible with Onyx Tier 3.
    """
    if not SERPAPI_KEY or SERPAPI_KEY.startswith("your_"):
        logger.debug("SERPAPI_KEY not configured. Skipping SerpAPI live search.")
        return []

    params = {
        "engine": "google_shopping",
        "q": query,
        "location": "India",
        "gl": "in",
        "hl": "en",
        "api_key": SERPAPI_KEY,
        "direct_link": "true",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.get(SERPAPI_ENDPOINT, params=params)

            if response.status_code != 200:
                logger.warning("SerpAPI request failed with status %d: %s", response.status_code, response.text[:200])
                return []

            data = response.json()
            shopping_results = data.get("shopping_results", [])
            results = []

            for item in shopping_results[:max_results]:
                price_str = item.get("price") or item.get("extracted_price")
                raw_price = None

                if isinstance(price_str, (int, float)):
                    raw_price = float(price_str)
                elif isinstance(price_str, str):
                    # Clean currency symbols and commas: ₹ 1,85,000 -> 185000
                    cleaned = re.sub(r"[^\d.]", "", price_str)
                    try:
                        raw_price = float(cleaned)
                    except ValueError:
                        continue

                if not raw_price or raw_price <= 0:
                    continue

                source_merchant = item.get("source") or item.get("merchant", {}).get("name") or "Google Shopping Merchant"
                link = item.get("link") or item.get("product_link")

                results.append({
                    "source_name": f"Google Shopping ({source_merchant})",
                    "price": raw_price,
                    "currency": "INR",
                    "confidence": "HIGH",
                    "reliability": "HIGH",
                    "evidence_url": link,
                    "title": item.get("title", query),
                    "is_demo_data": False,
                })

            logger.info("SerpAPI returned %d valid Google Shopping results for '%s'", len(results), query)
            return results

    except httpx.TimeoutException:
        logger.warning("SerpAPI timeout for query '%s'", query)
        return []
    except Exception as e:
        logger.warning("SerpAPI search failed for '%s': %s", query, e)
        return []
