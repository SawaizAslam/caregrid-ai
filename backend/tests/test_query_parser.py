"""Smoke tests for the rule-based query parser."""

from __future__ import annotations

from backend.app.query_parser import parse_query


def test_icu_oxygen_in_bihar_with_urgency():
    q = parse_query("nearest ICU hospital in Bihar with oxygen")
    d = q.to_dict()
    assert d["state"] == "Bihar"
    assert "icu" in d["specialties"]
    assert "oxygen" in d["requirements"]
    assert d["sort"] == "distance"
    # "nearest" + no explicit km -> default radius from config
    assert d["radius_km"] is not None and d["radius_km"] > 0


def test_dialysis_with_radius_and_pin():
    q = parse_query("dialysis center within 30km of 800001 with nephrologist")
    d = q.to_dict()
    assert d["pin"] == "800001"
    assert d["radius_km"] == 30
    assert "dialysis" in d["specialties"]
    assert "nephrology" in d["specialties"]
    assert d["sort"] == "distance"


def test_trauma_24_7_no_state():
    q = parse_query("trauma hospital open 24/7")
    d = q.to_dict()
    assert "trauma" in d["specialties"]
    # "24/7" hits the urgency keyword -> sort = distance
    assert d["sort"] == "distance"
    assert d["state"] is None
    assert d["pin"] is None


def test_relevance_default_when_no_urgency():
    q = parse_query("good cardiology hospital in Maharashtra")
    d = q.to_dict()
    assert d["state"] == "Maharashtra"
    assert "cardiology" in d["specialties"]
    assert d["sort"] == "relevance"


def test_state_abbreviation_up():
    q = parse_query("icu in UP")
    d = q.to_dict()
    assert d["state"] == "Uttar Pradesh"
    assert "icu" in d["specialties"]


def test_ventilator_synonym():
    q = parse_query("hospital with vent and o2")
    d = q.to_dict()
    assert "ventilator" in d["requirements"]
    assert "oxygen" in d["requirements"]
