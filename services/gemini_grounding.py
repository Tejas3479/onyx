"""Gemini Search Grounding Service for Tier 4 Non-Standard & Defense Items.

Queries Google Gemini API with Google Search Grounding to estimate reasonable budgetary
benchmarks for rare, non-standard, or specialized defense electronics (e.g. Waveguides, SDRs).
Gracefully falls back if GEMINI_API_KEY is not set.
"""

import json
import logging
import os
import re
import typing

import httpx

logger = logging.getLogger("onyx.gemini_grounding")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"


async def estimate_non_standard_price_with_gemini(
    query: str,
    specs: dict[str, typing.Any] | None = None,
    timeout_sec: float = 8.0,
) -> dict[str, typing.Any] | None:
    """Use Gemini with search grounding to estimate budgetary price for rare/specialized items."""
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("your_"):
        logger.debug("GEMINI_API_KEY not configured. Skipping Gemini Search Grounding.")
        return None

    prompt = f"""
You are an expert Government of India Procurement Officer estimating the fair market price under GFR 2017 Rule 149(vii).
Analyze the following item and provide an estimated fair price in INR (Indian Rupees):
Item: {query}
Specifications: {json.dumps(specs or {})}

Provide your output ONLY as a valid JSON object with the following keys:
{{
  "estimated_unit_price_inr": <number>,
  "price_range_low_inr": <number>,
  "price_range_high_inr": <number>,
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "rationale": "<Brief statutory rationale citing market reference or landed import basis>"
}}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    try:
        url = f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}"
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            res = await client.post(url, json=payload)
            if res.status_code != 200:
                logger.warning(
                    "Gemini API error (%d): %s", res.status_code, res.text[:200]
                )
                return None

            data = res.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                return None

            text = parts[0].get("text", "").strip()
            # Extract JSON substring
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                price = parsed.get("estimated_unit_price_inr")
                if price and float(price) > 0:
                    logger.info(
                        "Gemini Search Grounding estimated %s for '%s'", price, query
                    )
                    return {
                        "source_name": "Gemini Search Grounding (Statutory AI Estimator)",
                        "price": float(price),
                        "price_range_low": float(
                            parsed.get("price_range_low_inr", price * 0.9)
                        ),
                        "price_range_high": float(
                            parsed.get("price_range_high_inr", price * 1.15)
                        ),
                        "currency": "INR",
                        "confidence": parsed.get("confidence", "MEDIUM"),
                        "reliability": "HIGH",
                        "evidence_url": "https://ai.google.dev/gemini-api/docs/grounding",
                        "rationale": parsed.get(
                            "rationale",
                            f"GFR Tier 4 estimate based on search-grounded market synthesis for '{query}'.",
                        ),
                        "is_demo_data": False,
                    }

    except Exception as e:
        logger.warning("Gemini Search Grounding failed for '%s': %s", query, e)

    return None
