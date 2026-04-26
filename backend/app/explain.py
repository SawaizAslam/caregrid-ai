"""Build human-readable ``explanation`` strings + ``matched_features`` lists.

This module is small on purpose: judges want a clean one-liner that says *why*
each hospital surfaced. We piece it together from the structured signals the
ranker already computed.
"""

from __future__ import annotations

from typing import Any


def matched_features(
    *,
    query_specialties: list[str],
    query_equipment: list[str],
    hospital_specialty_tags: set[str],
    hospital_equipment_tags: set[str],
) -> list[str]:
    """Return the canonical tags that the query asked for AND the hospital has."""
    matched: list[str] = []
    for tag in query_specialties:
        if tag in hospital_specialty_tags:
            matched.append(tag)
    for tag in query_equipment:
        if tag in hospital_equipment_tags:
            matched.append(tag)
    return matched


def _pretty(tags: list[str]) -> str:
    pretty = [t.replace("_", " ").upper() if t in {"icu", "mri", "ct_scan"} else t.replace("_", " ").title() for t in tags]
    return ", ".join(pretty)


def build_explanation(
    *,
    hospital: dict[str, Any],
    matched: list[str],
    distance_km: float | None,
    trust_score: int,
    location_label: str | None,
    is_urgent: bool,
) -> str:
    parts: list[str] = []

    if matched:
        parts.append(f"Matches {_pretty(matched)}")
    else:
        # Fall back to whatever tags the hospital does have, so the user still
        # sees *why* it ranked at all (semantic similarity only).
        existing = sorted(set(hospital.get("specialty_tags", "").split(", ")) - {""})
        if existing:
            parts.append(f"Related services: {_pretty(existing[:3])}")
        else:
            parts.append("Semantic match on free-text notes")

    if location_label:
        if distance_km is not None:
            parts.append(f"in {location_label}, {distance_km:.1f} km away")
        else:
            parts.append(f"in {location_label}")
    elif distance_km is not None:
        parts.append(f"{distance_km:.1f} km away")

    if trust_score >= 80:
        parts.append(f"trust {trust_score}/100 (strong)")
    elif trust_score >= 50:
        parts.append(f"trust {trust_score}/100 (moderate)")
    else:
        parts.append(f"trust {trust_score}/100 (low - data gaps)")

    if is_urgent:
        parts.append("ranked for urgency / proximity")

    return ". ".join(parts) + "."
