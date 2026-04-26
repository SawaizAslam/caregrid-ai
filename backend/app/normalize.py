"""Controlled vocabulary + canonicalization for specialties and equipment.

Both the data loader and the query parser run free text through
:func:`canonicalize_specialties` / :func:`canonicalize_equipment` so we
match consistently at index time and at query time.
"""

from __future__ import annotations

import re
from typing import Iterable

# ---------------------------------------------------------------------------
# Canonical vocabulary -> list of synonyms / surface forms
# ---------------------------------------------------------------------------
SPECIALTY_SYNONYMS: dict[str, list[str]] = {
    "icu": ["icu", "intensive care", "critical care", "ccu", "intensive care unit"],
    "dialysis": ["dialysis", "haemodialysis", "hemodialysis", "kidney care"],
    "trauma": ["trauma", "trauma center", "trauma centre", "accident"],
    "cardiology": ["cardiology", "cardiac", "heart", "cath lab"],
    "neurology": ["neurology", "neuro", "neurosurgery", "brain"],
    "oncology": ["oncology", "cancer", "chemotherapy", "chemo"],
    "pediatrics": ["pediatrics", "paediatrics", "pediatric", "paediatric", "child", "neonatal", "nicu"],
    "maternity": ["maternity", "obstetrics", "gynaecology", "gynecology", "obg", "labour"],
    "orthopedics": ["orthopedics", "orthopaedics", "ortho", "bone", "fracture"],
    "nephrology": ["nephrology", "nephrologist", "renal"],
    "general_surgery": ["general surgery", "surgery", "operation theatre", "ot"],
    "emergency": ["emergency", "casualty", "er", "24/7", "24x7", "round the clock"],
}

EQUIPMENT_SYNONYMS: dict[str, list[str]] = {
    "oxygen": ["oxygen", "o2", "oxygen cylinder", "oxygen supply"],
    "ventilator": ["ventilator", "vent", "mechanical ventilator", "bipap", "cpap"],
    "mri": ["mri", "magnetic resonance"],
    "ct_scan": ["ct scan", "ct", "cat scan", "computed tomography"],
    "dialysis_machine": ["dialysis machine", "haemodialysis machine", "dialyser"],
    "xray": ["x-ray", "xray", "x ray", "radiography"],
    "ambulance": ["ambulance", "108", "patient transport"],
    "blood_bank": ["blood bank", "blood storage", "transfusion"],
}

# Specialties that count as "major" for the trust-score bonus
MAJOR_SPECIALTIES = {"icu", "dialysis", "trauma", "cardiology", "neurology"}

# Light stopword list applied before BM25 tokenization.
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "for", "to",
    "with", "near", "nearest", "by", "from", "is", "are", "be", "this",
    "that", "these", "those", "it", "as", "i", "we", "you", "my",
}


_CAMEL_BOUNDARY_LOWER_UPPER = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_CAMEL_BOUNDARY_UPPER_RUN = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")


def split_camel_case(text: str | None) -> str:
    """Insert spaces at camelCase boundaries.

    ``pediatricsAndStrabismusOphthalmology`` -> ``pediatrics And Strabismus Ophthalmology``
    ``CTScan`` -> ``CT Scan``. Returns an empty string for falsy input.
    """
    if not text:
        return ""
    out = _CAMEL_BOUNDARY_LOWER_UPPER.sub(" ", str(text))
    out = _CAMEL_BOUNDARY_UPPER_RUN.sub(" ", out)
    return out


def _lower(text: str | None) -> str:
    return (text or "").lower()


def canonicalize(text: str | None, vocab: dict[str, list[str]]) -> set[str]:
    """Return canonical tokens whose synonyms appear in ``text``.

    Handles camelCase tokens like ``familyMedicine`` /
    ``pediatricsAndStrabismusOphthalmology`` by inserting spaces at case
    boundaries before matching, so the existing word-boundary regexes work.
    """
    if not text:
        return set()
    haystack = " " + _lower(split_camel_case(text)) + " "
    found: set[str] = set()
    for canonical, synonyms in vocab.items():
        for syn in synonyms:
            # Word-boundary-aware substring match. We pad with spaces so a
            # plain `in` check works even for multi-word synonyms.
            if f" {syn} " in haystack or re.search(rf"\b{re.escape(syn)}\b", haystack):
                found.add(canonical)
                break
    return found


def canonicalize_specialties(text: str | None) -> set[str]:
    return canonicalize(text, SPECIALTY_SYNONYMS)


def canonicalize_equipment(text: str | None) -> set[str]:
    return canonicalize(text, EQUIPMENT_SYNONYMS)


def tokenize_for_bm25(text: str | None) -> list[str]:
    """Cheap whitespace tokenizer with light stopword removal."""
    if not text:
        return []
    cleaned = re.sub(r"[^a-z0-9\s]", " ", _lower(text))
    return [tok for tok in cleaned.split() if tok and tok not in STOPWORDS]


def join_unique(items: Iterable[str]) -> str:
    """Stable, deduplicated comma-joined view (used in explanations)."""
    seen: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return ", ".join(seen)
