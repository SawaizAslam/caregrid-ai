"""Aggregate statistics for the dashboard layer.

The challenge brief's third stretch goal is a Dynamic Crisis Map that
overlays the agent's findings on a map of India and highlights the highest-
risk medical deserts by PIN code or state. These helpers turn the indexed
DataFrame into a pre-aggregated payload the frontend can drop straight
into a choropleth or table.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from .data_loader import tags_to_set
from .geo import normalize_state_name
from .normalize import MAJOR_SPECIALTIES
from .query_parser import INDIAN_STATES

# Lower-cased canonical state set for the aggregator. Rows whose
# address_stateOrRegion is actually a city ("Ambernath", "Ayodhya") drop
# out of the desert map - they'd skew the choropleth otherwise.
_VALID_STATES_LC = {s.lower() for s in INDIAN_STATES}


def _has_major_specialty(tag_str: str | None) -> bool:
    return bool(tags_to_set(tag_str) & MAJOR_SPECIALTIES)


def _decode_breakdown(blob: Any) -> list[dict]:
    if not blob:
        return []
    if isinstance(blob, list):
        return [b for b in blob if isinstance(b, dict)]
    try:
        decoded = json.loads(blob)
        return decoded if isinstance(decoded, list) else []
    except (TypeError, ValueError):
        return []


def state_deserts(df: pd.DataFrame, *, top_n: int = 36) -> list[dict[str, Any]]:
    """Return per-state aggregates ranked by desert score (higher = worse)."""
    if df.empty:
        return []

    work = df.copy()
    work["state_norm"] = work["state"].fillna("").map(lambda s: (normalize_state_name(s) or s).strip().lower())
    work = work[work["state_norm"].isin(_VALID_STATES_LC)]

    grouped = work.groupby("state_norm")
    rows: list[dict[str, Any]] = []
    for state_lc, sub in grouped:
        n = len(sub)
        major_share = sub["specialty_tags_full"].fillna("").map(_has_major_specialty).mean()
        avg_trust = float(sub["trust_score"].mean()) if "trust_score" in sub else 0.0
        hospital_share = (
            (sub["facility_type"].fillna("").str.lower() == "hospital").mean() if "facility_type" in sub else 0.0
        )
        rows.append({
            "state": state_lc.title(),
            "facility_count": int(n),
            "hospital_count": int((sub["facility_type"].fillna("").str.lower() == "hospital").sum()) if "facility_type" in sub else int(n),
            "avg_trust_score": round(avg_trust, 1),
            "major_specialty_share": round(float(major_share), 3),
            "hospital_share": round(float(hospital_share), 3),
            # Higher = worse. Penalises states with low trust and/or low share of acute-care facilities.
            "desert_score": round(float((1 - major_share) * 0.5 + (1 - avg_trust / 100.0) * 0.5), 3),
        })

    rows.sort(key=lambda r: r["desert_score"], reverse=True)
    return rows[:top_n]


def specialty_gaps(df: pd.DataFrame, *, top_states_n: int = 20) -> dict[str, Any]:
    """Return a state x specialty matrix the dashboard can render as a heatmap.

    Shape:
        {
            "specialties": ["cardiology", "dialysis", ...],
            "states": ["Maharashtra", "Uttar Pradesh", ...],   # top-N states by total facility count
            "cells": [{"specialty": "icu", "state": "Bihar", "facility_count": 23}, ...],
            "summary": [
                {"specialty": "icu", "total_facilities": 324, "states_covered": 29, "top_states": [...]},
                ...
            ],
        }

    The optional ``summary`` list preserves the previous shape for any
    consumer that wants per-specialty headline numbers.
    """
    empty: dict[str, Any] = {"specialties": [], "states": [], "cells": [], "summary": []}
    if df.empty:
        return empty

    specialties = sorted(MAJOR_SPECIALTIES)

    per_specialty_state: dict[str, dict[str, int]] = {sp: {} for sp in specialties}
    state_totals: dict[str, int] = {}
    summary: list[dict[str, Any]] = []

    for specialty in specialties:
        mask = df["specialty_tags_full"].fillna("").map(lambda s, sp=specialty: sp in tags_to_set(s))
        subset = df[mask]
        per_state = per_specialty_state[specialty]
        for _, row in subset.iterrows():
            state = (normalize_state_name(row.get("state")) or row.get("state") or "").strip().title()
            if not state or state.lower() not in _VALID_STATES_LC:
                continue
            per_state[state] = per_state.get(state, 0) + 1
            state_totals[state] = state_totals.get(state, 0) + 1
        summary.append({
            "specialty": specialty,
            "total_facilities": int(len(subset)),
            "states_covered": int(len(per_state)),
            "top_states": sorted(per_state.items(), key=lambda kv: -kv[1])[:5],
        })

    states = [s for s, _ in sorted(state_totals.items(), key=lambda kv: -kv[1])[:top_states_n]]
    states_sorted = sorted(states)

    cells: list[dict[str, Any]] = []
    for specialty in specialties:
        per_state = per_specialty_state[specialty]
        for state in states_sorted:
            count = per_state.get(state, 0)
            if count == 0:
                continue
            cells.append({
                "specialty": specialty,
                "state": state,
                "facility_count": count,
            })

    return {
        "specialties": specialties,
        "states": states_sorted,
        "cells": cells,
        "summary": summary,
    }


def flagged_contradictions(df: pd.DataFrame, *, limit: int = 50) -> list[dict[str, Any]]:
    """Return rows whose trust breakdown contains a Contradiction rule."""
    if df.empty or "trust_breakdown_json" not in df.columns:
        return []

    flagged: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        breakdown = _decode_breakdown(row.get("trust_breakdown_json"))
        contradiction = next(
            (item for item in breakdown if "contradiction" in item.get("rule", "").lower()),
            None,
        )
        if not contradiction:
            continue
        flagged.append({
            "hospital_id": int(row.get("hospital_id", 0)),
            "hospital_name": row.get("hospital_name", ""),
            "state": row.get("state") or None,
            "district": row.get("district") or None,
            "pin_code": row.get("pin_code") or None,
            "trust_score": int(row.get("trust_score", 0)),
            "rule": contradiction.get("rule", ""),
            "evidence": contradiction.get("evidence", ""),
        })
        if len(flagged) >= limit:
            break
    return flagged


def overview(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"total": 0}
    facility_breakdown = (
        df["facility_type"].fillna("").str.lower().value_counts().to_dict()
        if "facility_type" in df.columns
        else {}
    )
    return {
        "total": int(len(df)),
        "facility_types": {k or "unknown": int(v) for k, v in facility_breakdown.items()},
        "avg_trust_score": round(float(df["trust_score"].mean()), 1) if "trust_score" in df else 0.0,
        "states_represented": int(df["state"].fillna("").map(lambda s: bool(s)).sum() and df["state"].nunique()),
    }
