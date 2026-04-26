"""Central configuration: paths, scoring weights, model + index settings."""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = Path(os.getenv("CAREGRID_DATA_DIR", PROJECT_ROOT / "data"))
INDEX_DIR = DATA_DIR / "index"

# Hospital dataset is auto-discovered: first match in this priority list wins.
HOSPITAL_DATASET_CANDIDATES = [
    DATA_DIR / "hospitals.csv",
    DATA_DIR / "hospitals.xlsx",
    DATA_DIR / "hospitals.xls",
]

PINCODES_PATH = DATA_DIR / "pincodes.csv"

# Persisted index artifacts
FAISS_INDEX_PATH = INDEX_DIR / "faiss.index"
META_PATH = INDEX_DIR / "meta.parquet"
BM25_PATH = INDEX_DIR / "bm25.pkl"
ENCODER_STATE_PATH = INDEX_DIR / "encoder.pkl"  # only used by the TF-IDF/SVD fallback

# ---------------------------------------------------------------------------
# Embedding model
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = os.getenv("CAREGRID_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = 384
EMBEDDING_BATCH_SIZE = 64

# ---------------------------------------------------------------------------
# Search / ranking
# ---------------------------------------------------------------------------
TOP_K_FAISS = 200          # candidates pulled from FAISS before reranking
TOP_K_RESULTS = 10         # final results returned to the client
DEFAULT_RADIUS_KM = 30     # used when query says "nearest" without a number

# Hybrid score weights (must sum to 1.0 for the relevance branch)
W_SEMANTIC = 0.5
W_KEYWORD = 0.2
W_TRUST = 0.2
W_LOCATION = 0.1

# When the parser flags urgency / "nearest", we re-weight to favour proximity
W_URGENT_LOC = 0.7
W_URGENT_TRUST = 0.2
W_URGENT_SEM = 0.1

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ORIGINS = os.getenv("CAREGRID_CORS_ORIGINS", "*").split(",")


def ensure_dirs() -> None:
    """Create data + index dirs if they don't exist (idempotent)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)


def find_hospital_dataset() -> Path | None:
    """Return the first existing hospital dataset path, or None."""
    for candidate in HOSPITAL_DATASET_CANDIDATES:
        if candidate.exists():
            return candidate
    return None
