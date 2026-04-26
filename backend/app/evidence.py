"""Source-sentence evidence for trust score rules.

The challenge brief asks for "row-level and step-level citations" -- if the
agent flags a hospital, it must show the exact sentence in the medical
report that justifies the score. This module produces those citations
deterministically so we don't depend on a hosted LLM.

For each canonical signal (major specialty, equipment, staffing,
contradiction, missing-fields) we scan the row's free-text fields
(``notes`` / ``description`` / ``capability`` / ``procedure``) and return the
shortest sentence that contains the matching token(s). When no sentence is
found we fall back to the raw value of the field that the rule is based on.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .normalize import (
    EQUIPMENT_SYNONYMS,
    MAJOR_SPECIALTIES,
    SPECIALTY_SYNONYMS,
    split_camel_case,
)

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+|\|")
_STAFF_HINTS = ("doctor", "nurse", "staff", "physician", "specialist", "consultant", "anesthesiologist")


def _gather_text(row: dict[str, Any], *fields: str) -> str:
    parts = []
    for f in fields:
        v = row.get(f)
        if v is None:
            continue
        s = str(v).strip()
        if not s or s in {"[]", "null", "nan", "None"}:
            continue
        parts.append(split_camel_case(s))
    return ". ".join(parts)


def _split_sentences(text: str) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    for chunk in _SENT_SPLIT.split(text):
        chunk = chunk.strip(" -•·\t,;")
        if chunk and len(chunk) > 4:
            out.append(chunk)
    return out


def _find_sentence(sentences: list[str], needles: Iterable[str]) -> str | None:
    """Return the shortest sentence that contains any of the needle phrases."""
    needles_lc = [n.lower() for n in needles if n]
    matches: list[str] = []
    for sent in sentences:
        sent_lc = sent.lower()
        if any(n in sent_lc for n in needles_lc):
            matches.append(sent)
    if not matches:
        return None
    matches.sort(key=len)
    return matches[0][:240]


def _all_synonyms(canonical_tags: Iterable[str], vocab: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for tag in canonical_tags:
        out.extend(vocab.get(tag, [tag]))
    return out


def _truncate(s: str, n: int = 240) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "..."


def evidence_for_specialty(row: dict[str, Any], specialty_tags: set[str]) -> str | None:
    """Best sentence justifying a major-specialty match for the row."""
    major_hits = sorted(specialty_tags & MAJOR_SPECIALTIES)
    if not major_hits:
        return None
    text = _gather_text(row, "notes", "description", "capability", "procedure", "specialties")
    sentences = _split_sentences(text)
    needles = _all_synonyms(major_hits, SPECIALTY_SYNONYMS)
    quote = _find_sentence(sentences, needles)
    if quote:
        return _truncate(quote)
    return _truncate(", ".join(major_hits).upper() + " — listed in specialty tags")


def evidence_for_equipment(row: dict[str, Any], equipment_tags: set[str]) -> str | None:
    text = _gather_text(row, "notes", "description", "capability", "procedure", "equipment")
    sentences = _split_sentences(text)
    if equipment_tags:
        needles = _all_synonyms(equipment_tags, EQUIPMENT_SYNONYMS)
        quote = _find_sentence(sentences, needles)
        if quote:
            return _truncate(quote)
    # Equipment-equivalent capabilities ("performs MRI", "round-the-clock oxygen", etc.)
    fallback_needles = ["mri", "ct ", "x-ray", "xray", "ventilator", "oxygen", "dialysis", "scan", "lab"]
    quote = _find_sentence(sentences, fallback_needles)
    if quote:
        return _truncate(quote)
    raw_eq = (row.get("equipment") or "").strip()
    if raw_eq and raw_eq != "[]":
        return _truncate(raw_eq)
    return None


def evidence_for_staff(row: dict[str, Any]) -> str | None:
    text = _gather_text(row, "staff", "notes", "description", "capability")
    sentences = _split_sentences(text)
    quote = _find_sentence(sentences, _STAFF_HINTS)
    if quote:
        return _truncate(quote)
    raw_staff = (row.get("staff") or "").strip()
    if raw_staff and raw_staff != "[]":
        return _truncate(f"Staff field: {raw_staff}")
    return None


def evidence_for_contradiction(row: dict[str, Any], specialty_tags: set[str]) -> str | None:
    """Quote the major-specialty claim that lacks supporting equipment/staff."""
    claim_tags = sorted(specialty_tags & MAJOR_SPECIALTIES)
    if not claim_tags:
        return None
    claim_text = evidence_for_specialty(row, set(claim_tags)) or ", ".join(claim_tags)
    return _truncate(
        f"Claim: \"{claim_text}\" -- but no equipment or staffing details were extracted from the notes."
    )


def evidence_for_missing(row: dict[str, Any], missing_count: int) -> str | None:
    if missing_count <= 0:
        return None
    fields = []
    for label, key in [
        ("specialties", "specialties"),
        ("equipment", "equipment"),
        ("staff", "staff"),
        ("notes", "notes"),
        ("location", "state"),
    ]:
        v = (row.get(key) or "").strip()
        if not v or v in {"[]", "null", "nan", "None"}:
            fields.append(label)
    return _truncate(f"Missing canonical fields: {', '.join(fields) or 'multiple'}")
