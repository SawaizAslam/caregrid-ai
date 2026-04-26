"""Geo helpers: PIN -> coords, state -> coords, haversine, location score.

The bundled ``data/pincodes.csv`` ships with ~80 curated rows (one per state /
UT plus major cities). For sharper distance estimates the user can replace it
with a fuller PIN dataset from data.gov.in - the loader is identical.
"""

from __future__ import annotations

import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .config import PINCODES_PATH


_STATE_ALIASES: dict[str, str] = {
    "ap": "andhra pradesh",
    "ar": "arunachal pradesh",
    "as": "assam",
    "br": "bihar",
    "ct": "chhattisgarh",
    "cg": "chhattisgarh",
    "ga": "goa",
    "gj": "gujarat",
    "hr": "haryana",
    "hp": "himachal pradesh",
    "jh": "jharkhand",
    "jk": "jammu and kashmir",
    "j&k": "jammu and kashmir",
    "ka": "karnataka",
    "kl": "kerala",
    "mp": "madhya pradesh",
    "mh": "maharashtra",
    "mn": "manipur",
    "ml": "meghalaya",
    "mz": "mizoram",
    "nl": "nagaland",
    "od": "odisha",
    "or": "odisha",
    "pb": "punjab",
    "rj": "rajasthan",
    "sk": "sikkim",
    "tn": "tamil nadu",
    "tg": "telangana",
    "ts": "telangana",
    "tr": "tripura",
    "up": "uttar pradesh",
    "uk": "uttarakhand",
    "ut": "uttarakhand",
    "wb": "west bengal",
    "dl": "delhi",
    "ch": "chandigarh",
    "py": "puducherry",
    "pondicherry": "puducherry",
    "an": "andaman and nicobar islands",
    "andaman": "andaman and nicobar islands",
    "ld": "lakshadweep",
    "la": "ladakh",
    "dn": "dadra and nagar haveli and daman and diu",
}


class GeoIndex:
    """Lookup PIN / state -> coordinates, with PIN-prefix fallback."""

    def __init__(self, pins: pd.DataFrame):
        self.pins = pins
        # Exact 6-digit lookup
        self._by_pin: dict[str, tuple[float, float, str, str]] = {
            str(row.pin_code).zfill(6): (row.latitude, row.longitude, row.state, row.district)
            for row in pins.itertuples(index=False)
        }
        # 3-digit prefix -> list of (lat, lon) for averaging
        prefix_buckets: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for row in pins.itertuples(index=False):
            prefix_buckets[str(row.pin_code).zfill(6)[:3]].append((row.latitude, row.longitude))
        self._by_prefix: dict[str, tuple[float, float]] = {
            prefix: (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
            for prefix, pts in prefix_buckets.items()
        }
        # State centroid (average of its bundled rows)
        state_buckets: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for row in pins.itertuples(index=False):
            state_buckets[row.state.lower()].append((row.latitude, row.longitude))
        self._by_state: dict[str, tuple[float, float]] = {
            state: (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
            for state, pts in state_buckets.items()
        }
        # District centroid
        district_buckets: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for row in pins.itertuples(index=False):
            district_buckets[row.district.lower()].append((row.latitude, row.longitude))
        self._by_district: dict[str, tuple[float, float]] = {
            district: (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
            for district, pts in district_buckets.items()
        }

    # ---------------------------------------------------------------------
    # Public lookups
    # ---------------------------------------------------------------------
    def pin_to_coords(self, pin: str | None) -> tuple[float, float] | None:
        if not pin:
            return None
        pin_clean = "".join(ch for ch in str(pin) if ch.isdigit())
        if len(pin_clean) < 3:
            return None
        pin6 = pin_clean.zfill(6)[:6]
        if pin6 in self._by_pin:
            lat, lon, *_ = self._by_pin[pin6]
            return (lat, lon)
        prefix = pin6[:3]
        return self._by_prefix.get(prefix)

    def state_to_coords(self, state: str | None) -> tuple[float, float] | None:
        if not state:
            return None
        return self._by_state.get(state.strip().lower())

    def district_to_coords(self, district: str | None) -> tuple[float, float] | None:
        if not district:
            return None
        return self._by_district.get(district.strip().lower())


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_geo_index(path: str | None = None) -> GeoIndex:
    pins_path = Path(path) if path else PINCODES_PATH
    if not pins_path.exists():
        raise FileNotFoundError(
            f"pincodes.csv not found at {pins_path}. The repo ships a curated default."
        )
    df = pd.read_csv(pins_path, dtype={"pin_code": str})
    df["pin_code"] = df["pin_code"].astype(str).str.strip().str.zfill(6)
    df["state"] = df["state"].astype(str).str.strip()
    df["district"] = df["district"].astype(str).str.strip()
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    return GeoIndex(df)


# ---------------------------------------------------------------------------
# Haversine
# ---------------------------------------------------------------------------
EARTH_RADIUS_KM = 6371.0088


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    lat1, lon1 = a
    lat2, lon2 = b
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_state_name(value: str | None) -> str | None:
    """Map abbreviations / common variants to canonical state name (lowercase)."""
    if not value:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    return _STATE_ALIASES.get(cleaned, cleaned)


def hospital_coords(row) -> tuple[float, float] | None:
    """Best-effort coords for a hospital row.

    Priority: explicit lat/lon -> PIN -> district -> state.
    Accepts either a pandas Series/namedtuple or any object with the right attrs.
    """
    geo = get_geo_index()

    def _attr(obj, name):
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)

    lat = _attr(row, "latitude")
    lon = _attr(row, "longitude")
    try:
        if lat is not None and lon is not None and not (math.isnan(float(lat)) or math.isnan(float(lon))):
            return (float(lat), float(lon))
    except (TypeError, ValueError):
        pass

    coords = geo.pin_to_coords(_attr(row, "pin_code"))
    if coords:
        return coords
    coords = geo.district_to_coords(_attr(row, "district"))
    if coords:
        return coords
    return geo.state_to_coords(_attr(row, "state"))


def location_score(
    hospital_row,
    *,
    query_state: str | None,
    query_pin: str | None,
    radius_km: float | None,
) -> tuple[float, float | None]:
    """Return ``(score in [0, 1], distance_km or None)`` for a hospital row.

    - PIN + radius given: score = max(0, 1 - dist / radius); distance reported.
    - Else state match: 1.0 (district fall-through 0.5).
    - Else 0.
    """
    geo = get_geo_index()

    if query_pin:
        q_coords = geo.pin_to_coords(query_pin)
        h_coords = hospital_coords(hospital_row)
        if q_coords and h_coords:
            dist = haversine_km(q_coords, h_coords)
            if radius_km and radius_km > 0:
                return (max(0.0, 1.0 - dist / radius_km), dist)
            # No radius => smooth decay so closer is still better
            return (1.0 / (1.0 + dist / 50.0), dist)

    if query_state:
        q_state = normalize_state_name(query_state)
        h_state = normalize_state_name(getattr(hospital_row, "state", None) or (hospital_row.get("state") if isinstance(hospital_row, dict) else None))
        if q_state and h_state and q_state == h_state:
            return (1.0, None)
        # district fallback
        h_district = (
            (hospital_row.get("district") if isinstance(hospital_row, dict) else getattr(hospital_row, "district", None)) or ""
        ).strip().lower()
        if h_district and q_state and h_district == q_state:
            return (0.5, None)

    return (0.0, None)
