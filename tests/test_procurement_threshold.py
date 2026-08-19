"""Tests for the GFR procurement-threshold compliance evaluation."""

from services.procurement_threshold import evaluate_procurement_threshold


def test_direct_purchase_below_25k():
    r = evaluate_procurement_threshold(20000, quotes_obtained=1, price_found=True)
    assert r["mode"] == "direct_purchase"
    assert r["rule"] == "GFR 2017 Rule 161"
    assert r["min_quotes_required"] == 0
    assert r["compliant"] is True


def test_direct_purchase_no_price_found():
    r = evaluate_procurement_threshold(20000, quotes_obtained=0, price_found=False)
    assert r["mode"] == "direct_purchase"
    assert r["compliant"] is False
    assert r["non_compliance"] is not None


def test_limited_tender_25k_to_250k():
    r = evaluate_procurement_threshold(80000, quotes_obtained=3, price_found=True)
    assert r["mode"] == "limited_tender"
    assert r["rule"] == "GFR 2017 Rule 162"
    assert r["min_quotes_required"] == 3
    assert r["quotes_obtained"] == 3
    assert r["compliant"] is True


def test_limited_tender_insufficient_quotes():
    r = evaluate_procurement_threshold(80000, quotes_obtained=1, price_found=True)
    assert r["mode"] == "limited_tender"
    assert r["compliant"] is False
    assert "at least 3" in r["non_compliance"]


def test_competitive_bidding_above_250k():
    r = evaluate_procurement_threshold(600000, quotes_obtained=4, price_found=True)
    assert r["mode"] == "competitive_bidding"
    assert r["rule"] == "GFR 2017 Rule 163"
    assert r["compliant"] is True


def test_competitive_bidding_boundary_250k():
    r = evaluate_procurement_threshold(250000, quotes_obtained=3, price_found=True)
    assert r["mode"] == "limited_tender"
    r2 = evaluate_procurement_threshold(250000.01, quotes_obtained=3, price_found=True)
    assert r2["mode"] == "competitive_bidding"


def test_none_value_returns_none():
    assert evaluate_procurement_threshold(None, quotes_obtained=4, price_found=True) is None