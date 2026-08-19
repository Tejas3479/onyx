from services.freight_estimator import _region_for, estimate_freight


def test_metro_city_low_freight():
    est = estimate_freight("New Delhi", 288000, quantity=1)
    assert est is not None
    assert est["region_label"] == "Metro city (local road)"
    assert est["freight_pct"] == 0.6
    assert est["freight_amount"] == 1728.0
    assert est["landed_total"] == 289728.0
    assert est["is_demo_simulated"] is True


def test_north_east_transit_premium():
    est = estimate_freight("Guwahati, Assam", 100000)
    assert est is not None
    assert est["region_label"] == "North-East (transit premium)"
    assert est["freight_pct"] == 2.2
    assert est["freight_amount"] == 2200.0


def test_island_sea_freight_highest():
    est = estimate_freight("Port Blair, Andaman", 100000)
    assert est is not None
    assert est["region_label"] == "Island Territory (sea freight)"
    assert est["freight_pct"] == 4.5
    assert est["freight_amount"] == 4500.0


def test_default_interstate():
    est = estimate_freight("Nagpur", 50000, quantity=3)
    assert est is not None
    assert est["region_label"] == "Inter-state (road/rail)"
    assert est["freight_pct"] == 1.2
    assert est["goods_value"] == 150000.0
    assert est["landed_total"] == 151800.0


def test_no_location_or_price_returns_none():
    assert estimate_freight(None, 1000) is None
    assert estimate_freight("New Delhi", None) is None
    assert estimate_freight("", 1000) is None


def test_region_bucketing_matches_estimate():
    label, pct = _region_for("andaman islands")
    assert "Island" in label and pct == 4.5
    label, pct = _region_for("mumbai")
    assert "Metro" in label and pct == 0.6
    label, pct = _region_for("assam")
    assert "North-East" in label and pct == 2.2
    label, pct = _region_for("jaipur")
    assert "Metro" in label and pct == 0.6