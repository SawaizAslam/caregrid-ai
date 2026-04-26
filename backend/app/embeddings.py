"""Text encoder + FAISS index (build / save / load / search).

Two backends are available, auto-selected at runtime:

1. **MiniLM** (preferred) - ``sentence-transformers/all-MiniLM-L6-v2`` via
   ``sentence_transformers``. CPU only, 384-d. True semantic embeddings.

2. **TF-IDF + TruncatedSVD** (fallback) - sklearn-based, fitted on the
   corpus. 384-d output to stay drop-in compatible with the FAISS index.
   Used when the torch DLL stack is broken / unavailable on the host
   (common on bleeding-edge Python 3.14 Windows builds).

Both encoders produce ``float32`` vectors that are L2-normalized, so the
existing ``IndexFlatIP`` continues to give cosine-similarity rankings.
"""

from __future__ import annotations

import logging
import os
import pickle
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable

import numpy as np

from .config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    FAISS_INDEX_PATH,
    INDEX_DIR,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Encoder interface
# ---------------------------------------------------------------------------
class BaseEncoder(ABC):
    """Common interface for the encoder backends."""

    name: str = "base"
    dim: int = EMBEDDING_DIM

    @abstractmethod
    def fit(self, texts: list[str]) -> None:
        """Fit on the corpus. No-op for pre-trained models like MiniLM."""

    @abstractmethod
    def encode(self, texts: Iterable[str], *, batch_size: int = EMBEDDING_BATCH_SIZE) -> np.ndarray:
        """Encode -> ``float32`` matrix, rows L2-normalised."""

    def save(self, path: Path) -> None:
        """Persist any fitted state. No-op by default."""
        return

    def load(self, path: Path) -> None:
        """Load any fitted state. No-op by default."""
        return


# ---------------------------------------------------------------------------
# MiniLM (sentence-transformers) backend
# ---------------------------------------------------------------------------
class MiniLMEncoder(BaseEncoder):
    name = "sentence-transformers/all-MiniLM-L6-v2"
    dim = 384

    def __init__(self, model_name: str = EMBEDDING_MODEL):
        from sentence_transformers import SentenceTransformer  # noqa: WPS433

        logger.info("Loading embedding model: %s", model_name)
        self._model = SentenceTransformer(model_name, device="cpu")
        self.name = model_name

    def fit(self, texts: list[str]) -> None:
        return  # pre-trained, nothing to fit

    def encode(self, texts: Iterable[str], *, batch_size: int = EMBEDDING_BATCH_SIZE) -> np.ndarray:
        cleaned = [t if t else " " for t in texts]
        vectors = self._model.encode(
            cleaned,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype("float32")
        return vectors


# ---------------------------------------------------------------------------
# TF-IDF + TruncatedSVD fallback (no torch / no onnxruntime needed)
# ---------------------------------------------------------------------------
class TfidfSvdEncoder(BaseEncoder):
    name = "tfidf-svd-fallback"
    dim = EMBEDDING_DIM  # 384 by default - matches MiniLM output

    def __init__(self, dim: int = EMBEDDING_DIM):
        self.dim = dim
        self._vectorizer = None
        self._svd = None

    def fit(self, texts: list[str]) -> None:
        from sklearn.decomposition import TruncatedSVD  # noqa: WPS433
        from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: WPS433

        cleaned = [t if t else " " for t in texts]
        vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            max_features=50_000,
            min_df=2,
            sublinear_tf=True,
            stop_words="english",
        )
        tfidf = vectorizer.fit_transform(cleaned)
        # SVD components must be < min(rows, vocab); cap defensively.
        n_components = max(2, min(self.dim, tfidf.shape[1] - 1, max(2, tfidf.shape[0] - 1)))
        svd = TruncatedSVD(n_components=n_components, random_state=42)
        svd.fit(tfidf)
        self._vectorizer = vectorizer
        self._svd = svd
        # Store the actual achieved dim
        self.dim = n_components
        logger.info(
            "Fitted TF-IDF/SVD encoder: vocab=%d, dim=%d", len(vectorizer.vocabulary_), n_components
        )

    def encode(self, texts: Iterable[str], *, batch_size: int = EMBEDDING_BATCH_SIZE) -> np.ndarray:
        if self._vectorizer is None or self._svd is None:
            raise RuntimeError("TfidfSvdEncoder not fitted. Call fit(corpus) first.")
        cleaned = [t if t else " " for t in texts]
        tfidf = self._vectorizer.transform(cleaned)
        dense = self._svd.transform(tfidf).astype("float32")
        # L2-normalise rows so IndexFlatIP gives cosine.
        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        norms[norms < 1e-9] = 1.0
        return dense / norms

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump({"vectorizer": self._vectorizer, "svd": self._svd, "dim": self.dim}, fh)

    def load(self, path: Path) -> None:
        with open(path, "rb") as fh:
            state = pickle.load(fh)
        self._vectorizer = state["vectorizer"]
        self._svd = state["svd"]
        self.dim = int(state.get("dim", self.dim))


# ---------------------------------------------------------------------------
# Auto-selecting singleton
# ---------------------------------------------------------------------------
ENCODER_STATE_PATH = INDEX_DIR / "encoder.pkl"

_encoder: BaseEncoder | None = None


def _select_encoder() -> BaseEncoder:
    """Try MiniLM; fall back to TF-IDF on any import / load failure."""
    backend = os.getenv("CAREGRID_ENCODER", "auto").lower()
    if backend in {"tfidf", "fallback", "sklearn"}:
        logger.info("CAREGRID_ENCODER=%s -> using TF-IDF/SVD fallback.", backend)
        return TfidfSvdEncoder()
    try:
        return MiniLMEncoder()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "MiniLM encoder unavailable (%s: %s). Falling back to TF-IDF/SVD.",
            type(exc).__name__,
            exc,
        )
        return TfidfSvdEncoder()


def get_encoder() -> BaseEncoder:
    """Return the active encoder (loaded on first use, cached thereafter)."""
    global _encoder
    if _encoder is None:
        _encoder = _select_encoder()
    return _encoder


def reset_encoder() -> None:
    """Drop the cached encoder so the next call re-selects (mostly for tests)."""
    global _encoder
    _encoder = None


def encode_texts(texts: Iterable[str], *, batch_size: int = EMBEDDING_BATCH_SIZE) -> np.ndarray:
    """Encode a list of strings -> ``float32`` matrix, L2-normalized."""
    encoder = get_encoder()
    return encoder.encode(list(texts), batch_size=batch_size)


# ---------------------------------------------------------------------------
# FAISS helpers (unchanged shape)
# ---------------------------------------------------------------------------
def build_faiss_index(vectors: np.ndarray):
    """Create an ``IndexFlatIP`` over the (already-normalized) vectors."""
    import faiss

    if vectors.dtype != np.float32:
        vectors = vectors.astype("float32")
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    return index


def save_index(index, path: Path = FAISS_INDEX_PATH) -> None:
    import faiss

    path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(path))


def load_index(path: Path = FAISS_INDEX_PATH):
    import faiss

    if not path.exists():
        raise FileNotFoundError(f"FAISS index not found at {path}")
    return faiss.read_index(str(path))


def search_index(index, query_vec: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (scores, ids) for the top-k matches."""
    if query_vec.ndim == 1:
        query_vec = query_vec.reshape(1, -1)
    if query_vec.dtype != np.float32:
        query_vec = query_vec.astype("float32")
    scores, ids = index.search(query_vec, top_k)
    return scores, ids
