"""Regression test for the TF-IDF/SVD fallback encoder.

Ensures the fallback path (used when torch/onnxruntime can't load) produces
L2-normalised vectors and ranks an obviously-relevant document above an
obviously-unrelated one - same contract as the MiniLM backend.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

pytest.importorskip("sklearn")

from backend.app.embeddings import TfidfSvdEncoder  # noqa: E402


CORPUS = [
    "Patna ICU hospital with ventilator and oxygen 24x7 emergency",
    "Patna ICU centre intensive care unit ventilator support oxygen",
    "Gaya dialysis center with nephrologist on staff renal care",
    "Gaya kidney dialysis hospital nephrologist hemodialysis",
    "Mumbai trauma care level-1 trauma centre blood bank",
    "Mumbai accident emergency trauma surgery operation theatre",
    "Bengaluru general clinic basic services x-ray radiology",
    "Bengaluru small clinic dental services general practice",
    "Chennai cardiac surgery hospital with cath lab heart",
    "Chennai cardiology heart hospital cath lab cardiac care",
    "Delhi multi-specialty hospital ICU trauma cardiology neurology",
    "Hyderabad pediatric hospital children NICU neonatal care",
]


def test_fallback_encoder_fits_and_encodes():
    enc = TfidfSvdEncoder(dim=32)
    enc.fit(CORPUS)
    vecs = enc.encode(CORPUS)
    assert vecs.shape[0] == len(CORPUS)
    assert vecs.dtype == np.float32
    # Rows are L2-normalised.
    norms = np.linalg.norm(vecs, axis=1)
    assert all(math.isclose(n, 1.0, abs_tol=1e-4) for n in norms)


def test_fallback_encoder_relevance():
    enc = TfidfSvdEncoder(dim=32)
    enc.fit(CORPUS)
    doc_vecs = enc.encode(CORPUS)
    query_vec = enc.encode(["dialysis nephrologist"])[0]
    sims = doc_vecs @ query_vec
    top_idx = int(np.argmax(sims))
    # The dialysis row should beat the unrelated rows.
    assert "dialysis" in CORPUS[top_idx].lower()


def test_fallback_encoder_save_load_roundtrip(tmp_path):
    enc = TfidfSvdEncoder(dim=32)
    enc.fit(CORPUS)
    before = enc.encode(["icu oxygen"])
    state_path = tmp_path / "encoder.pkl"
    enc.save(state_path)

    restored = TfidfSvdEncoder(dim=32)
    restored.load(state_path)
    after = restored.encode(["icu oxygen"])
    assert np.allclose(before, after, atol=1e-6)


def test_unfitted_encoder_raises():
    enc = TfidfSvdEncoder(dim=16)
    with pytest.raises(RuntimeError):
        enc.encode(["anything"])
