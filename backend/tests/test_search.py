"""End-to-end smoke test for the search engine on a tiny synthetic dataset.

This test exercises the full pipeline (loader -> embeddings -> FAISS -> BM25 ->
trust score -> ranker -> explainer). It needs ``sentence-transformers`` and
``faiss-cpu`` installed, and on first run will download the MiniLM weights
(~90 MB). The test is auto-skipped if either dep is missing.
"""

from __future__ import annotations

import pytest

pytest.importorskip("sentence_transformers")
pytest.importorskip("faiss")

from backend.app.search import SearchEngine  # noqa: E402


SYNTHETIC_CSV = """hospital_name,state,district,pin_code,specialties,equipment,notes,staff
Patna ICU Hospital,Bihar,Patna,800001,"ICU, cardiology","ventilator, oxygen","Round the clock ICU with 20 doctors and 60 nurses",20 doctors 60 nurses
Gaya Dialysis Center,Bihar,Gaya,823001,"dialysis, nephrology","dialysis machine","Dedicated kidney care, 5 nephrologists",5 nephrologists
Mumbai Trauma Care,Maharashtra,Mumbai,400001,"trauma, emergency","ventilator, oxygen, blood bank","24x7 trauma center with 50 staff",50 staff
Bangalore General Clinic,Karnataka,Bengaluru,560001,"general surgery","x-ray","Small clinic, basic services",
"""


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("caregrid")
    csv_path = tmp / "hospitals.csv"
    csv_path.write_text(SYNTHETIC_CSV, encoding="utf-8")
    return SearchEngine.build(csv_path)


def test_icu_bihar_query_returns_patna(engine):
    payload = engine.search("nearest ICU hospital in Bihar with oxygen")
    results = payload["results"]
    assert results, "Should return at least one result"
    top = results[0]
    assert "Patna" in top["hospital_name"], f"Expected Patna ICU on top, got {top['hospital_name']}"
    assert "icu" in top["matched_features"]
    assert "oxygen" in top["matched_features"]
    assert top["trust_score"] > 0
    assert payload["query_understood"]["state"] == "Bihar"


def test_dialysis_query_finds_gaya(engine):
    payload = engine.search("dialysis center with nephrologist in Bihar")
    top = payload["results"][0]
    assert "Gaya" in top["hospital_name"]
    assert "dialysis" in top["matched_features"]


def test_state_filter_excludes_other_states(engine):
    payload = engine.search("ICU in Karnataka")
    states = {r["state"] for r in payload["results"]}
    assert states == {"Karnataka"} or states.issubset({"Karnataka"}), \
        f"State filter should only include Karnataka rows, got {states}"


def test_response_shape_matches_spec(engine):
    payload = engine.search("trauma hospital open 24/7")
    assert "results" in payload
    for r in payload["results"]:
        for key in ("hospital_name", "score", "trust_score", "explanation",
                    "location", "matched_features"):
            assert key in r, f"missing key {key} in result"
        assert isinstance(r["score"], float)
        assert 0 <= r["trust_score"] <= 100
