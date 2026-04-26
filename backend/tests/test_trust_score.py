"""Tests for the trust score engine."""

from __future__ import annotations

from backend.app.trust_score import compute_trust


def _row(**kwargs):
    base = {
        "specialties": "",
        "equipment": "",
        "notes": "",
        "staff": "",
        "state": "Bihar",
        "pin_code": "800001",
        "specialty_tags_full": "",
        "equipment_tags_full": "",
    }
    base.update(kwargs)
    return base


def test_full_record_high_score():
    # Spec baseline: +20 specialty + +20 equipment + +20 staff = 60.
    # Tie-breaker bonus on top adds a few more, so >= 60 is the safe floor.
    row = _row(
        specialties="ICU, cardiology",
        equipment="ventilator, oxygen",
        notes="40 doctors and 100 nurses on staff",
        staff="40 doctors, 100 nurses",
        specialty_tags_full="cardiology, icu",
        equipment_tags_full="oxygen, ventilator",
    )
    result = compute_trust(row)
    assert result.score >= 60
    rules = " ".join(item["rule"] for item in result.breakdown)
    assert "Major specialty" in rules
    assert "Equipment info present" in rules
    assert "Staffing info present" in rules


def test_contradiction_penalized():
    # Claims ICU but no equipment AND no staff info.
    row = _row(
        specialties="ICU available",
        equipment="",
        notes="",
        staff="",
        specialty_tags_full="icu",
        equipment_tags_full="",
    )
    result = compute_trust(row)
    rules = " ".join(item["rule"] for item in result.breakdown)
    assert "Contradiction" in rules
    # +20 (specialty) - 30 (contradiction) = -10 -> clamped to 0
    assert result.score <= 10


def test_missing_fields_penalty():
    row = _row(
        specialties="",
        equipment="",
        notes="",
        staff="",
        state="",
        pin_code="",
    )
    result = compute_trust(row)
    rules = " ".join(item["rule"] for item in result.breakdown)
    assert "missing fields" in rules.lower()
    assert result.score == 0


def test_score_clamped_to_range():
    # Even an extremely rich record must stay within [0, 100].
    row = _row(
        specialties="ICU, cardiology, neurology, trauma, dialysis",
        equipment="oxygen, ventilator, MRI, CT scan, dialysis machine, blood bank",
        notes="200 doctors and 500 nurses on staff",
        staff="200 doctors, 500 nurses",
        specialty_tags_full="cardiology, dialysis, icu, neurology, trauma",
        equipment_tags_full="blood_bank, ct_scan, dialysis_machine, mri, oxygen, ventilator",
    )
    result = compute_trust(row)
    assert 0 <= result.score <= 100
    assert result.score >= 60
