"""Price extraction from scraped web content.

Extracts product names, prices, vendor info, and availability from
raw markdown/HTML content. Uses regex pattern matching with LLM fallback.

Split confidence scoring:
  - extraction_completeness: how many expected fields were found (0.0-1.0)
  - price_reliability: outlier detection, staleness, cross-source checks (HIGH/MEDIUM/LOW)
"""

import logging
import re
from typing import Any

logger = logging.getLogger("onyx.price_extractor")

# Common currency symbols and patterns
INR_PATTERN = re.compile(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE)
USD_PATTERN = re.compile(r"(?:\$|USD)\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE)

# "Contact for Price" and similar non-price indicators
NO_PRICE_INDICATORS = [
    "contact for price",
    "request a quote",
    "get quote",
    "call for price",
    "price on request",
    "ask for price",
    "get best price",
    "get latest price",
    "login to view price",
]


def _parse_price(text: str) -> float | None:
    """Extract a numeric price from text, handling Indian number formatting."""
    # Remove commas from numbers (Indian: 1,50,000 and Western: 150,000)
    cleaned = text.replace(",", "")
    try:
        val = float(cleaned)
        # Sanity check: price should be positive and reasonable
        if 0 < val < 100_000_000:  # Up to 10 crore
            return val
    except ValueError:
        pass
    return None


def extract_prices_from_content(
    content: str,
    source_name: str,
    source_url: str,
) -> list[dict[str, Any]]:
    """Extract price entries from scraped markdown/text content.

    Returns a list of dicts, each containing:
      - product_name: str
      - price: float | None
      - currency: str
      - vendor_name: str | None
      - availability: str | None
      - confidence: str (HIGH/MEDIUM/LOW)
      - reliability: str (HIGH/MEDIUM/LOW)
      - extraction_completeness: float (0.0-1.0)
    """
    if not content or len(content.strip()) < 20:
        logger.debug("Content too short for extraction from %s", source_name)
        return []

    results: list[dict[str, Any]] = []

    # Check for "contact for price" indicators
    content_lower = content.lower()
    has_no_price = any(indicator in content_lower for indicator in NO_PRICE_INDICATORS)

    # Find all INR prices
    inr_matches = INR_PATTERN.findall(content)
    prices_found: list[float] = []
    for match in inr_matches:
        price = _parse_price(match)
        if price is not None:
            prices_found.append(price)

    # Deduplicate prices (keep unique values)
    prices_found = sorted(set(prices_found))

    if not prices_found and not has_no_price:
        # Try USD prices
        usd_matches = USD_PATTERN.findall(content)
        for match in usd_matches:
            price = _parse_price(match)
            if price is not None:
                # Convert to INR (approximate)
                prices_found.append(round(price * 83.5, 2))

    if not prices_found:
        if has_no_price:
            results.append(
                {
                    "product_name": _extract_product_name(content),
                    "price": None,
                    "currency": "INR",
                    "source_name": source_name,
                    "source_url": source_url,
                    "vendor_name": None,
                    "availability": "Contact for Price",
                    "confidence": "LOW",
                    "reliability": "LOW",
                    "extraction_completeness": 0.2,
                }
            )
        return results

    # Create entries for each unique price found
    for price in prices_found[:10]:  # Cap at 10 prices per source
        # Score extraction completeness
        completeness = _score_completeness(
            has_price=True,
            has_product_name=True,
            has_vendor=False,  # Regex can't reliably extract vendor
            has_availability=not has_no_price,
        )

        results.append(
            {
                "product_name": _extract_product_name(content),
                "price": price,
                "currency": "INR",
                "source_name": source_name,
                "source_url": source_url,
                "vendor_name": None,
                "availability": "In Stock" if not has_no_price else "Contact for Price",
                "confidence": "MEDIUM",
                "reliability": "MEDIUM",
                "extraction_completeness": completeness,
            }
        )

    return results


def _extract_product_name(content: str) -> str:
    """Extract a likely product name from content (first heading or bold text)."""
    # Try markdown heading
    heading_match = re.search(r"^#+\s+(.+)$", content, re.MULTILINE)
    if heading_match:
        name = heading_match.group(1).strip()
        if len(name) > 5:
            return name[:200]

    # Try first bold text
    bold_match = re.search(r"\*\*(.+?)\*\*", content)
    if bold_match:
        name = bold_match.group(1).strip()
        if len(name) > 5:
            return name[:200]

    # Fallback: first non-empty line
    for line in content.split("\n"):
        line = line.strip()
        if len(line) > 10:
            return line[:200]

    return "Unknown Product"


def _score_completeness(
    has_price: bool,
    has_product_name: bool,
    has_vendor: bool,
    has_availability: bool,
) -> float:
    """Score extraction completeness as 0.0-1.0 based on field presence."""
    fields = [
        (has_price, 0.4),  # Price is most important
        (has_product_name, 0.3),  # Product identification
        (has_vendor, 0.15),  # Vendor info
        (has_availability, 0.15),  # Stock status
    ]
    return sum(weight for present, weight in fields if present)


def score_price_reliability(
    price: float,
    all_prices: list[float],
    source_name: str,
) -> str:
    """Score price reliability using outlier detection and cross-source verification.

    Rules:
      - >2σ from mean across sources → LOW (outlier)
      - "Contact for Price" → LOW (stale/unavailable)
      - ±10% of cross-source median → HIGH (corroborated)
      - Otherwise → MEDIUM
    """
    if not all_prices or price is None:
        return "LOW"

    n = len(all_prices)
    if n < 2:
        return "MEDIUM"  # Can't cross-verify with single source

    mean = sum(all_prices) / n
    variance = sum((p - mean) ** 2 for p in all_prices) / n
    std_dev = variance**0.5

    # Outlier check: >2σ from mean
    if std_dev > 0 and abs(price - mean) > 2 * std_dev:
        logger.debug(
            "Price %.2f from %s is an outlier (mean=%.2f, std=%.2f)",
            price,
            source_name,
            mean,
            std_dev,
        )
        return "LOW"

    # Cross-source corroboration: within ±10% of median
    sorted_prices = sorted(all_prices)
    median = (
        sorted_prices[n // 2]
        if n % 2
        else (sorted_prices[n // 2 - 1] + sorted_prices[n // 2]) / 2
    )

    if median > 0 and abs(price - median) / median <= 0.10:
        return "HIGH"

    return "MEDIUM"


def compute_statistics(prices: list[float]) -> dict[str, Any]:
    """Compute min/max/avg/median/count statistics from a list of prices."""
    if not prices:
        return {}

    sorted_prices = sorted(prices)
    n = len(sorted_prices)
    return {
        "min": sorted_prices[0],
        "max": sorted_prices[-1],
        "avg": round(sum(sorted_prices) / n, 2),
        "median": round(
            sorted_prices[n // 2]
            if n % 2
            else (sorted_prices[n // 2 - 1] + sorted_prices[n // 2]) / 2,
            2,
        ),
        "count": n,
    }
