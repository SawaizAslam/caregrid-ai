"""Regression tests for the dataset-shape patches (G3 + G4)."""

from __future__ import annotations

from backend.app.data_loader import _flatten_json_list
from backend.app.normalize import (
    canonicalize_equipment,
    canonicalize_specialties,
    split_camel_case,
)


# ---------------------------------------------------------------------------
# G3: JSON-list flattening
# ---------------------------------------------------------------------------
def test_flatten_simple_list():
    assert _flatten_json_list('["familyMedicine","endodontics"]') == "familyMedicine endodontics"


def test_flatten_empty_list_becomes_empty_string():
    assert _flatten_json_list("[]") == ""


def test_flatten_passthrough_for_non_list_text():
    assert _flatten_json_list("just plain text") == "just plain text"


def test_flatten_passthrough_for_invalid_json():
    # Looks like a list but isn't valid JSON -> returned unchanged.
    assert _flatten_json_list("[not json,really]") == "[not json,really]"


def test_flatten_handles_quoted_facts():
    raw = '["Has 1 ophthalmologist on staff","Performs cataract surgery"]'
    out = _flatten_json_list(raw)
    assert "ophthalmologist" in out
    assert "cataract surgery" in out


# ---------------------------------------------------------------------------
# G4: camelCase splitting
# ---------------------------------------------------------------------------
def test_split_basic_camel():
    assert split_camel_case("familyMedicine") == "family Medicine"


def test_split_long_compound():
    out = split_camel_case("pediatricsAndStrabismusOphthalmology")
    assert "pediatrics" in out.lower()
    assert "ophthalmology" in out.lower()


def test_split_acronym_then_word():
    # "CTScan" -> "CT Scan", not "C T Scan".
    assert split_camel_case("CTScan") == "CT Scan"


def test_canonicalise_picks_up_camel_specialty():
    # Real token from the dataset: pediatrics nested inside a compound.
    found = canonicalize_specialties("pediatricsAndStrabismusOphthalmology")
    assert "pediatrics" in found


def test_canonicalise_picks_up_trauma_inside_compound():
    found = canonicalize_specialties("eyeTraumaAndEmergencyEyeCare")
    assert "trauma" in found
    assert "emergency" in found


def test_canonicalise_equipment_from_capability_text():
    # capability sentences mention equipment in free text.
    found = canonicalize_equipment(
        "Performs MRI and CT scan; has dedicated ambulance service"
    )
    assert {"mri", "ct_scan", "ambulance"}.issubset(found)
