"""Column-tolerant hospital dataset loader + cleaning.

The real-world dataset will arrive with inconsistent column names; we resolve
each canonical field by trying a list of aliases. After this stage every
downstream module sees the same schema.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .config import find_hospital_dataset
from .normalize import (
    canonicalize_equipment,
    canonicalize_specialties,
    join_unique,
)

# Canonical columns -> list of accepted aliases (lower-cased, stripped).
# The first match in each list wins.
COLUMN_ALIASES: dict[str, list[str]] = {
    "hospital_name": [
        "hospital_name", "hospital name", "name", "hospital", "hosp_name",
        "facility", "facility_name", "facility name", "institution",
    ],
    "state": [
        "state", "state_name", "state name",
        "address_stateorregion", "address_state", "stateorregion",
    ],
    "district": [
        "district", "district_name", "district name", "city",
        "address_city",
    ],
    "pin_code": [
        "pin_code", "pincode", "pin code", "pin", "zip", "postal_code", "postal code",
        "address_ziporpostcode", "ziporpostcode", "address_postcode",
    ],
    "address": [
        "address", "addr", "location_address", "full_address",
        "address_line1",
    ],
    "specialties": [
        "specialties", "specialty", "speciality", "specialities",
        "services", "departments", "department",
    ],
    "equipment": [
        "equipment", "equipments", "facilities", "infrastructure",
        "amenities", "resources",
    ],
    "procedure": [
        "procedure", "procedures",
    ],
    "capability": [
        "capability", "capabilities",
    ],
    "notes": ["notes", "description", "remarks", "about", "details", "comments"],
    "staff": [
        "staff", "staffing", "staff_count", "staff count",
        "doctors", "nurses", "personnel", "manpower",
        "numberdoctors", "number_doctors", "doctor_count", "physicians",
    ],
    "facility_type": [
        "facility_type", "facilitytypeid", "facility_type_id", "type",
    ],
    "phone": [
        "phone", "contact", "phone_number", "phone number", "mobile",
        "officialphone", "official_phone", "phone_numbers",
    ],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lon", "lng", "long"],
}

REQUIRED_COLUMNS = list(COLUMN_ALIASES.keys())


def _read_any(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str)
    raise ValueError(f"Unsupported dataset extension: {suffix}")


def _resolve_columns(df: pd.DataFrame) -> dict[str, str | None]:
    """Map each canonical field to the actual column in ``df`` (or None)."""
    lowered = {col.strip().lower(): col for col in df.columns}
    resolved: dict[str, str | None] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        match: str | None = None
        for alias in aliases:
            if alias in lowered:
                match = lowered[alias]
                break
        resolved[canonical] = match
    return resolved


def _coerce_str(series: pd.Series | None, length: int) -> pd.Series:
    if series is None:
        return pd.Series([""] * length, dtype="object")
    return series.fillna("").astype(str).str.strip()


def _coerce_float(series: pd.Series | None, length: int) -> pd.Series:
    if series is None:
        return pd.Series([np.nan] * length, dtype="float64")
    return pd.to_numeric(series, errors="coerce")


_JSON_LIST_RE = re.compile(r"^\s*\[.*\]\s*$", re.DOTALL)


def _flatten_json_list(value: str) -> str:
    """If ``value`` is a JSON-encoded list, decode and return a space-joined string.

    Falls back to the original string when parsing fails or the field isn't a
    list. Nested lists / objects are stringified with ``json.dumps`` so their
    text content remains searchable.
    """
    if not value:
        return ""
    s = value.strip()
    if not s or not _JSON_LIST_RE.match(s):
        return s
    try:
        parsed = json.loads(s)
    except (ValueError, TypeError):
        return s
    if not isinstance(parsed, list):
        return s
    parts: list[str] = []
    for item in parsed:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, (int, float, bool)):
            parts.append(str(item))
        else:
            parts.append(json.dumps(item, ensure_ascii=False))
    return " ".join(p for p in parts if p)


def _coerce_list_str(series: pd.Series | None, length: int) -> pd.Series:
    """String coerce + JSON-list flatten in one pass."""
    if series is None:
        return pd.Series([""] * length, dtype="object")
    return series.fillna("").astype(str).str.strip().apply(_flatten_json_list)


def load_hospitals(path: Path | None = None) -> pd.DataFrame:
    """Load + normalize the hospital dataset.

    Returns a DataFrame with the canonical schema and a ``search_text`` field
    used by the embedding + BM25 indexes. Each row also gets a stable
    ``hospital_id`` (its row index) and pre-computed canonical specialty /
    equipment sets so downstream filters and trust scoring don't re-tokenize.
    """
    dataset_path = path or find_hospital_dataset()
    if dataset_path is None or not dataset_path.exists():
        raise FileNotFoundError(
            "No hospital dataset found. Drop hospitals.csv or hospitals.xlsx into the data/ "
            "folder (or set CAREGRID_DATA_DIR)."
        )

    raw = _read_any(dataset_path)
    raw.columns = [str(c).strip() for c in raw.columns]
    resolved = _resolve_columns(raw)
    n = len(raw)

    out = pd.DataFrame(
        {
            "hospital_name": _coerce_str(raw[resolved["hospital_name"]] if resolved["hospital_name"] else None, n),
            "state": _coerce_str(raw[resolved["state"]] if resolved["state"] else None, n),
            "district": _coerce_str(raw[resolved["district"]] if resolved["district"] else None, n),
            "pin_code": _coerce_str(raw[resolved["pin_code"]] if resolved["pin_code"] else None, n),
            "address": _coerce_str(raw[resolved["address"]] if resolved["address"] else None, n),
            # JSON-list fields: decode + flatten so canonicalisation can see the tokens.
            "specialties": _coerce_list_str(raw[resolved["specialties"]] if resolved["specialties"] else None, n),
            "equipment": _coerce_list_str(raw[resolved["equipment"]] if resolved["equipment"] else None, n),
            "procedure": _coerce_list_str(raw[resolved["procedure"]] if resolved["procedure"] else None, n),
            "capability": _coerce_list_str(raw[resolved["capability"]] if resolved["capability"] else None, n),
            "notes": _coerce_str(raw[resolved["notes"]] if resolved["notes"] else None, n),
            "staff": _coerce_list_str(raw[resolved["staff"]] if resolved["staff"] else None, n),
            "facility_type": _coerce_str(raw[resolved.get("facility_type")] if resolved.get("facility_type") else None, n),
            "phone": _coerce_list_str(raw[resolved["phone"]] if resolved["phone"] else None, n),
            "latitude": _coerce_float(raw[resolved["latitude"]] if resolved["latitude"] else None, n),
            "longitude": _coerce_float(raw[resolved["longitude"]] if resolved["longitude"] else None, n),
        }
    )

    # Drop fully empty rows (no name AND no specialty/notes/equipment).
    keep_mask = (
        out["hospital_name"].str.len().gt(0)
        | out["specialties"].str.len().gt(0)
        | out["notes"].str.len().gt(0)
        | out["equipment"].str.len().gt(0)
        | out["procedure"].str.len().gt(0)
        | out["capability"].str.len().gt(0)
    )
    out = out.loc[keep_mask].reset_index(drop=True)

    # Stable id == row index after cleaning.
    out["hospital_id"] = out.index.astype(int)

    # Lower-cased helpers for matching (kept separate from display strings).
    out["state_lc"] = out["state"].str.lower()
    out["district_lc"] = out["district"].str.lower()
    out["pin_code"] = out["pin_code"].str.replace(r"\.0$", "", regex=True).str.strip()

    # Canonical sets (stored as comma-joined strings for parquet friendliness).
    out["specialty_tags"] = out["specialties"].apply(
        lambda t: join_unique(sorted(canonicalize_specialties(t)))
    )
    out["equipment_tags"] = out["equipment"].apply(
        lambda t: join_unique(sorted(canonicalize_equipment(t)))
    )
    # The "_full" tags fold in every text field that can plausibly mention a
    # specialty or piece of equipment - this is what trust_score and the
    # explainer consume so dental / clinic rows don't get unfairly penalised.
    full_text_series = (
        out["specialties"].fillna("") + " "
        + out["procedure"].fillna("") + " "
        + out["capability"].fillna("") + " "
        + out["notes"].fillna("")
    )
    out["specialty_tags_full"] = full_text_series.apply(
        lambda t: join_unique(sorted(canonicalize_specialties(t)))
    )
    full_equipment_series = (
        out["equipment"].fillna("") + " "
        + out["procedure"].fillna("") + " "
        + out["capability"].fillna("") + " "
        + out["notes"].fillna("")
    )
    out["equipment_tags_full"] = full_equipment_series.apply(
        lambda t: join_unique(sorted(canonicalize_equipment(t)))
    )

    # Combined free text used for embeddings + BM25. Keep human-readable.
    out["search_text"] = (
        out["hospital_name"].fillna("")
        + " | " + out["specialties"].fillna("")
        + " | " + out["equipment"].fillna("")
        + " | " + out["procedure"].fillna("")
        + " | " + out["capability"].fillna("")
        + " | " + out["notes"].fillna("")
        + " | " + out["facility_type"].fillna("")
        + " | " + out["state"].fillna("")
        + " " + out["district"].fillna("")
    ).str.strip()

    return out


def tags_to_set(tag_string: str | None) -> set[str]:
    """Parse the comma-joined canonical tag string back into a set."""
    if not tag_string:
        return set()
    return {t.strip() for t in tag_string.split(",") if t.strip()}
