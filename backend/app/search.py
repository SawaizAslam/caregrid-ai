"""Search orchestrator: parse -> filter -> hybrid score -> rank -> explain.

The :class:`SearchEngine` owns the in-memory state (DataFrame, FAISS index,
BM25 index, encoder) and is constructed once at app startup.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .bm25_index import build_bm25, load_bm25, save_bm25, score_query
from .config import (
    BM25_PATH,
    ENCODER_STATE_PATH,
    FAISS_INDEX_PATH,
    META_PATH,
    TOP_K_FAISS,
    TOP_K_RESULTS,
)
from .data_loader import load_hospitals, tags_to_set
from .embeddings import (
    TfidfSvdEncoder,
    build_faiss_index,
    encode_texts,
    get_encoder,
    load_index,
    save_index,
    search_index,
)
from .explain import build_explanation, matched_features
from .geo import (
    get_geo_index,
    hospital_coords,
    haversine_km,
    location_score,
    normalize_state_name,
)
from .query_parser import ParsedQuery, parse_query
from .ranker import combine_scores
from .trust_score import attach_trust_scores

logger = logging.getLogger(__name__)


@dataclass
class _IndexBundle:
    df: pd.DataFrame
    faiss_index: object
    bm25: object


class SearchEngine:
    def __init__(self, df: pd.DataFrame, faiss_index, bm25):
        self.df = df.reset_index(drop=True)
        self.faiss_index = faiss_index
        self.bm25 = bm25
        # Pre-warm geo cache so the first query isn't slow.
        get_geo_index()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    @classmethod
    def build(cls, dataset_path: Path | None = None) -> "SearchEngine":
        """Load dataset and build all indexes from scratch."""
        logger.info("Loading hospital dataset...")
        df = load_hospitals(dataset_path)
        logger.info("Loaded %d hospital rows.", len(df))

        logger.info("Computing trust scores...")
        df = attach_trust_scores(df)

        encoder = get_encoder()
        # TF-IDF backend needs a fit pass; MiniLM's fit is a no-op.
        if isinstance(encoder, TfidfSvdEncoder):
            logger.info("Fitting TF-IDF/SVD encoder on corpus...")
            encoder.fit(df["search_text"].tolist())

        logger.info("Encoding %d texts with %s...", len(df), encoder.name)
        vectors = encode_texts(df["search_text"].tolist())

        logger.info("Building FAISS index...")
        faiss_index = build_faiss_index(vectors)

        logger.info("Building BM25 index...")
        bm25 = build_bm25(df["search_text"].tolist())

        return cls(df, faiss_index, bm25)

    @classmethod
    def from_disk_or_build(cls, dataset_path: Path | None = None) -> "SearchEngine":
        """Reuse cached indexes if all artifacts exist, otherwise rebuild + persist."""
        if META_PATH.exists() and FAISS_INDEX_PATH.exists() and BM25_PATH.exists():
            try:
                logger.info("Loading cached indexes from %s", META_PATH.parent)
                df = pd.read_parquet(META_PATH)
                faiss_index = load_index()
                bm25 = load_bm25()
                # If the active encoder is the TF-IDF fallback, restore its
                # fitted state from disk; otherwise the singleton needs no help.
                encoder = get_encoder()
                if isinstance(encoder, TfidfSvdEncoder) and ENCODER_STATE_PATH.exists():
                    encoder.load(ENCODER_STATE_PATH)
                return cls(df, faiss_index, bm25)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Cached index load failed (%s) - rebuilding", exc)

        engine = cls.build(dataset_path)
        engine.persist()
        return engine

    def persist(self) -> None:
        META_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_parquet(META_PATH, index=False)
        save_index(self.faiss_index)
        save_bm25(self.bm25)
        # Persist encoder state too, but only when it carries fitted parameters.
        encoder = get_encoder()
        if isinstance(encoder, TfidfSvdEncoder):
            encoder.save(ENCODER_STATE_PATH)
        logger.info("Persisted indexes to %s", META_PATH.parent)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def _filter_candidates(self, parsed: ParsedQuery) -> np.ndarray:
        """Apply hard metadata filters and return surviving row indices."""
        df = self.df
        mask = np.ones(len(df), dtype=bool)

        if parsed.state:
            target = normalize_state_name(parsed.state)
            if target:
                # Compare against normalized hospital state.
                hosp_states = df["state_lc"].fillna("")
                mask &= np.array([
                    (normalize_state_name(s) or s) == target for s in hosp_states
                ])

        if parsed.pin and parsed.radius_km:
            geo = get_geo_index()
            q_coords = geo.pin_to_coords(parsed.pin)
            if q_coords:
                radius = float(parsed.radius_km)
                # Vectorized-ish loop (fine at 10k rows).
                inside: list[bool] = []
                for row in df.itertuples(index=False):
                    h = hospital_coords(row)
                    if h is None:
                        inside.append(False)
                        continue
                    inside.append(haversine_km(q_coords, h) <= radius)
                mask &= np.array(inside, dtype=bool)

        ids = np.flatnonzero(mask)
        # If the filter wiped everything (e.g. unknown state), fall back to no filter
        # so the user still gets *some* results rather than an empty list.
        if ids.size == 0:
            return np.arange(len(df))
        return ids

    def _semantic_scores(self, query_text: str) -> np.ndarray:
        """Full-corpus semantic score vector (length == len(df))."""
        qvec = encode_texts([query_text])
        # FAISS top-K, then fold back to a length-N score array (others = 0).
        scores, ids = search_index(self.faiss_index, qvec, top_k=min(TOP_K_FAISS, len(self.df)))
        out = np.zeros(len(self.df), dtype="float32")
        out[ids[0]] = scores[0]
        return out

    def search(self, query: str, *, top_k: int | None = None) -> dict:
        parsed = parse_query(query)
        candidates = self._filter_candidates(parsed)

        # Signal vectors over the FULL corpus, then sliced to candidates.
        sem_full = self._semantic_scores(query)
        bm25_full = score_query(self.bm25, query)

        # Trust score is precomputed.
        trust_full = self.df["trust_score"].to_numpy(dtype="float32")

        # Location score per candidate (cheap loop; 10k max).
        loc_full = np.zeros(len(self.df), dtype="float32")
        dist_full = np.full(len(self.df), np.nan, dtype="float64")
        for idx in candidates:
            row = self.df.iloc[idx]
            score, dist = location_score(
                row,
                query_state=parsed.state,
                query_pin=parsed.pin,
                radius_km=parsed.radius_km,
            )
            loc_full[idx] = score
            if dist is not None:
                dist_full[idx] = dist

        sem = sem_full[candidates]
        kw = bm25_full[candidates] if bm25_full.size else np.zeros(len(candidates), dtype="float32")
        trust = trust_full[candidates]
        loc = loc_full[candidates]

        urgent = parsed.sort == "distance"
        final_scores, components = combine_scores(
            semantic=sem, keyword=kw, trust=trust, location=loc, urgent=urgent
        )

        # Rank
        order = np.argsort(-final_scores)
        k = top_k or TOP_K_RESULTS
        top_idx_local = order[:k]
        top_global_ids = candidates[top_idx_local]

        results = []
        q_specialties = parsed.specialties
        q_equipment = parsed.requirements
        for local, global_id in zip(top_idx_local, top_global_ids):
            row = self.df.iloc[int(global_id)]
            row_dict = row.to_dict()

            specialty_tags = tags_to_set(row_dict.get("specialty_tags_full") or row_dict.get("specialty_tags"))
            equipment_tags = tags_to_set(row_dict.get("equipment_tags_full") or row_dict.get("equipment_tags"))
            matched = matched_features(
                query_specialties=q_specialties,
                query_equipment=q_equipment,
                hospital_specialty_tags=specialty_tags,
                hospital_equipment_tags=equipment_tags,
            )

            distance = dist_full[int(global_id)]
            distance_val = None if math.isnan(distance) else float(distance)

            location_bits = [b for b in [row_dict.get("district"), row_dict.get("state")] if b]
            location_label = ", ".join(location_bits) if location_bits else None

            explanation = build_explanation(
                hospital=row_dict,
                matched=matched,
                distance_km=distance_val,
                trust_score=int(row_dict.get("trust_score", 0)),
                location_label=location_label,
                is_urgent=urgent,
            )

            try:
                trust_breakdown = json.loads(row_dict.get("trust_breakdown_json") or "[]")
            except json.JSONDecodeError:
                trust_breakdown = []

            coords = hospital_coords(row)
            lat = coords[0] if coords else None
            lon = coords[1] if coords else None

            results.append({
                "hospital_id": int(row_dict.get("hospital_id", global_id)),
                "hospital_name": row_dict.get("hospital_name", ""),
                "score": float(final_scores[int(local)]),
                "trust_score": int(row_dict.get("trust_score", 0)),
                "explanation": explanation,
                "location": location_label or "",
                "state": row_dict.get("state") or None,
                "district": row_dict.get("district") or None,
                "pin_code": row_dict.get("pin_code") or None,
                "latitude": lat,
                "longitude": lon,
                "distance_km": distance_val,
                "matched_features": matched,
                "trust_breakdown": trust_breakdown,
                "score_components": {
                    "semantic": float(components["semantic"][int(local)]),
                    "keyword": float(components["keyword"][int(local)]),
                    "trust": float(components["trust"][int(local)]),
                    "location": float(components["location"][int(local)]),
                },
            })

        return {
            "results": results,
            "query_understood": parsed.to_dict(),
            "total_candidates": int(candidates.size),
        }

    # ------------------------------------------------------------------
    # Single-record fetch
    # ------------------------------------------------------------------
    def get_hospital(self, hospital_id: int) -> dict | None:
        match = self.df[self.df["hospital_id"] == hospital_id]
        if match.empty:
            return None
        row = match.iloc[0].to_dict()
        try:
            row["trust_breakdown"] = json.loads(row.get("trust_breakdown_json") or "[]")
        except json.JSONDecodeError:
            row["trust_breakdown"] = []
        row["specialty_tags"] = sorted(tags_to_set(row.get("specialty_tags_full") or row.get("specialty_tags")))
        row["equipment_tags"] = sorted(tags_to_set(row.get("equipment_tags_full") or row.get("equipment_tags")))
        coords = hospital_coords(match.iloc[0])
        if coords:
            row["latitude"] = coords[0]
            row["longitude"] = coords[1]
        return row
