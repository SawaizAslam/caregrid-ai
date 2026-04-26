"""Final hybrid ranking formula.

Per spec:
    final_score = 0.5*sem + 0.2*bm25 + 0.2*(trust/100) + 0.1*loc

If the parser flags urgency (sort == "distance"), we re-weight to favor
proximity over semantic relevance:
    final_score = 0.7*loc + 0.2*(trust/100) + 0.1*sem
"""

from __future__ import annotations

import numpy as np

from .config import (
    W_KEYWORD,
    W_LOCATION,
    W_SEMANTIC,
    W_TRUST,
    W_URGENT_LOC,
    W_URGENT_SEM,
    W_URGENT_TRUST,
)


def _minmax(arr: np.ndarray) -> np.ndarray:
    if arr.size == 0:
        return arr
    lo = float(np.min(arr))
    hi = float(np.max(arr))
    if hi - lo < 1e-9:
        return np.zeros_like(arr, dtype="float32") if hi == 0 else np.ones_like(arr, dtype="float32")
    return ((arr - lo) / (hi - lo)).astype("float32")


def combine_scores(
    *,
    semantic: np.ndarray,
    keyword: np.ndarray,
    trust: np.ndarray,        # 0..100
    location: np.ndarray,     # already 0..1
    urgent: bool,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Return (final_scores, normalized_components) for a candidate set."""
    sem_n = _minmax(semantic.astype("float32"))
    kw_n = _minmax(keyword.astype("float32"))
    loc_n = np.clip(location.astype("float32"), 0.0, 1.0)
    trust_n = np.clip(trust.astype("float32") / 100.0, 0.0, 1.0)

    if urgent:
        final = (
            W_URGENT_LOC * loc_n
            + W_URGENT_TRUST * trust_n
            + W_URGENT_SEM * sem_n
        )
    else:
        final = (
            W_SEMANTIC * sem_n
            + W_KEYWORD * kw_n
            + W_TRUST * trust_n
            + W_LOCATION * loc_n
        )

    components = {
        "semantic": sem_n,
        "keyword": kw_n,
        "trust": trust_n,
        "location": loc_n,
    }
    return final.astype("float32"), components
