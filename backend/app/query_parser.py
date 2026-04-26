"""Rule-based natural-language query parser.

Extracts structured intent from a free-text query like
"nearest ICU hospital in Bihar with oxygen" -> the JSON shape from the spec:

    {
      "state": "Bihar",
      "pin": null,
      "radius_km": 30,
      "specialties": ["icu"],
      "requirements": ["oxygen"],
      "sort": "distance",
      "raw_query": "..."
    }

Pure regex + vocabulary lookups - no LLM, fully offline.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .config import DEFAULT_RADIUS_KM
from .geo import normalize_state_name
from .normalize import (
    EQUIPMENT_SYNONYMS,
    SPECIALTY_SYNONYMS,
    canonicalize_equipment,
    canonicalize_specialties,
)

# Canonical Indian state / UT names, used for substring detection.
INDIAN_STATES = [
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
    "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
    "andaman and nicobar islands", "chandigarh",
    "dadra and nagar haveli and daman and diu", "delhi", "jammu and kashmir",
    "ladakh", "lakshadweep", "puducherry",
]

PIN_RE = re.compile(r"\b(\d{6})\b")
RADIUS_RE = re.compile(r"\bwithin\s+(\d+)\s*(?:km|kms|kilometers|kilometres)\b", re.IGNORECASE)
RADIUS_FALLBACK_RE = re.compile(r"\b(\d+)\s*(?:km|kms|kilometers|kilometres)\b", re.IGNORECASE)
URGENCY_RE = re.compile(
    r"\b(urgent|urgently|emergency|nearest|nearby|24/7|24x7|round the clock|asap|immediately)\b",
    re.IGNORECASE,
)


@dataclass
class ParsedQuery:
    raw_query: str
    state: str | None = None
    pin: str | None = None
    radius_km: float | None = None
    specialties: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    sort: str = "relevance"  # "relevance" or "distance"

    def to_dict(self) -> dict:
        d = asdict(self)
        # Match the spec's JSON shape exactly.
        return {
            "state": d["state"],
            "pin": d["pin"],
            "radius_km": d["radius_km"],
            "specialties": d["specialties"],
            "requirements": d["requirements"],
            "sort": d["sort"],
            "raw_query": d["raw_query"],
        }


def _detect_state(query_lc: str) -> str | None:
    # Longest-match wins so "andhra pradesh" beats "andhra".
    for state in sorted(INDIAN_STATES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(state)}\b", query_lc):
            return state.title()
    # Two-letter / common abbreviations are normalized via geo.normalize_state_name.
    for tok in re.findall(r"\b[a-z&]{2,3}\b", query_lc):
        canonical = normalize_state_name(tok)
        if canonical and canonical in INDIAN_STATES:
            return canonical.title()
    return None


def _detect_pin(query: str) -> str | None:
    m = PIN_RE.search(query)
    return m.group(1) if m else None


def _detect_radius(query: str, *, urgent: bool) -> float | None:
    m = RADIUS_RE.search(query) or RADIUS_FALLBACK_RE.search(query)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return float(DEFAULT_RADIUS_KM) if urgent else None


def parse_query(query: str) -> ParsedQuery:
    """Parse free text into a structured ``ParsedQuery``."""
    raw = (query or "").strip()
    lc = raw.lower()

    pin = _detect_pin(raw)
    state = _detect_state(lc)
    urgent = bool(URGENCY_RE.search(lc))
    radius = _detect_radius(lc, urgent=urgent or bool(pin))

    specialties = sorted(canonicalize_specialties(lc))
    requirements = sorted(canonicalize_equipment(lc))

    sort = "distance" if (urgent or pin) else "relevance"

    return ParsedQuery(
        raw_query=raw,
        state=state,
        pin=pin,
        radius_km=radius,
        specialties=specialties,
        requirements=requirements,
        sort=sort,
    )


# Re-export for convenience / docs
__all__ = [
    "ParsedQuery",
    "parse_query",
    "INDIAN_STATES",
    "SPECIALTY_SYNONYMS",
    "EQUIPMENT_SYNONYMS",
]
