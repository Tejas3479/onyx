"""GFR 2017 procurement-threshold compliance evaluation.

Value bands (goods):
  - Direct Purchase        : <= Rs 25,000            -> GFR Rule 161
  - Limited Tender Enquiry : Rs 25,000 - Rs 2.5 lakh -> GFR Rule 162
  - Open Competitive Bidding: > Rs 2.5 lakh          -> GFR Rule 163

For each band we state the minimum competitive evidence the procuring
authority must place on file, and whether the evidence the waterfall
actually gathered satisfies it.
"""

DIRECT_PURCHASE_LIMIT = 25_000.0
LIMITED_TENDER_LIMIT = 250_000.0
MIN_QUOTES_TENDER = 3


def evaluate_procurement_threshold(
    value: float | None,
    quotes_obtained: int = 0,
    price_found: bool = False,
) -> dict | None:
    """Return the applicable procurement mode + compliance verdict for a
    purchase value, or None when no value was supplied."""
    if value is None:
        return None

    if value <= DIRECT_PURCHASE_LIMIT:
        mode = "direct_purchase"
        rule = "GFR 2017 Rule 161"
        mode_label = "Direct Purchase (local market)"
        min_quotes = 0
        evidence_required = (
            "Single-source purchase is permitted without a competitive "
            "quotation; keep the receipt / local quotation on file."
        )
    elif value <= LIMITED_TENDER_LIMIT:
        mode = "limited_tender"
        rule = "GFR 2017 Rule 162"
        mode_label = "Limited Tender Enquiry"
        min_quotes = MIN_QUOTES_TENDER
        evidence_required = (
            "Written offers from at least 3 suppliers must be obtained and "
            "filed with the tender enquiry."
        )
    else:
        mode = "competitive_bidding"
        rule = "GFR 2017 Rule 163"
        mode_label = "Advertised / Open Competitive Bidding"
        min_quotes = MIN_QUOTES_TENDER
        evidence_required = (
            "Open tender with wide advertisement; L1 (Lowest-1) of a valid "
            "competitive pool must be determined from the received bids."
        )

    if mode == "direct_purchase":
        compliant = bool(price_found)
    else:
        compliant = bool(price_found) and quotes_obtained >= min_quotes

    non_compliance = None
    if not compliant:
        if not price_found:
            non_compliance = (
                "No verified price could be established. Obtain a local "
                "quotation (or wider tender enquiry) before proceeding."
            )
        elif quotes_obtained < min_quotes:
            non_compliance = (
                f"Only {quotes_obtained} independent source(s) verified — at "
                f"least {min_quotes} written offers are required for this "
                f"value band. Issue a broader tender enquiry before award."
            )

    return {
        "value": round(value, 2),
        "mode": mode,
        "mode_label": mode_label,
        "rule": rule,
        "min_quotes_required": min_quotes,
        "quotes_obtained": quotes_obtained,
        "compliant": compliant,
        "evidence_required": evidence_required,
        "non_compliance": non_compliance,
    }
