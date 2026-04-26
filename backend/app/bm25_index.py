"""BM25 keyword index built on the same ``search_text`` field as the embeddings.

Persisted as a pickled ``BM25Okapi`` so we can rebuild rapidly at startup
without re-tokenizing.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Iterable

import numpy as np
from rank_bm25 import BM25Okapi

from .config import BM25_PATH
from .normalize import tokenize_for_bm25


def build_bm25(texts: Iterable[str]) -> BM25Okapi:
    tokenized = [tokenize_for_bm25(t) for t in texts]
    return BM25Okapi(tokenized)


def save_bm25(bm25: BM25Okapi, path: Path = BM25_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump(bm25, fh)


def load_bm25(path: Path = BM25_PATH) -> BM25Okapi:
    if not path.exists():
        raise FileNotFoundError(f"BM25 index not found at {path}")
    with open(path, "rb") as fh:
        return pickle.load(fh)


def score_query(bm25: BM25Okapi, query: str, candidate_ids: np.ndarray | None = None) -> np.ndarray:
    """Return a BM25 score per document.

    If ``candidate_ids`` is provided, scores for non-candidates are returned as
    ``0.0`` so the caller can do a single-pass min-max normalization.
    """
    tokens = tokenize_for_bm25(query)
    if not tokens:
        # No keyword content -> uniform zero scores
        return np.zeros(len(bm25.doc_freqs) if hasattr(bm25, "doc_freqs") else 0, dtype="float32")
    scores = np.asarray(bm25.get_scores(tokens), dtype="float32")
    if candidate_ids is not None:
        mask = np.zeros_like(scores, dtype=bool)
        mask[candidate_ids] = True
        scores = np.where(mask, scores, 0.0)
    return scores
