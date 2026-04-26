"""Pydantic request / response models for the FastAPI endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Free-text user query")
    top_k: int | None = Field(default=None, ge=1, le=50, description="Override default top-K")


class TrustBreakdownItem(BaseModel):
    rule: str
    delta: int
    evidence: str = ""


class HospitalResult(BaseModel):
    hospital_id: int
    hospital_name: str
    score: float = Field(..., description="Final hybrid score in [0, 1]")
    trust_score: int
    explanation: str
    location: str
    state: str | None = None
    district: str | None = None
    pin_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    distance_km: float | None = None
    matched_features: list[str] = Field(default_factory=list)
    trust_breakdown: list[TrustBreakdownItem] = Field(default_factory=list)
    score_components: dict[str, float] = Field(default_factory=dict)


class QueryUnderstood(BaseModel):
    state: str | None
    pin: str | None
    radius_km: float | None
    specialties: list[str]
    requirements: list[str]
    sort: str
    raw_query: str


class SearchResponse(BaseModel):
    results: list[HospitalResult]
    query_understood: QueryUnderstood
    total_candidates: int


class HealthResponse(BaseModel):
    status: str
    dataset_rows: int
    faiss_loaded: bool
    embedding_model: str
    index_path: str
    pincodes_loaded: int


class HospitalDetail(BaseModel):
    hospital_id: int
    hospital_name: str
    state: str | None
    district: str | None
    pin_code: str | None
    address: str | None
    specialties: str | None
    equipment: str | None
    notes: str | None
    staff: str | None
    phone: str | None
    latitude: float | None
    longitude: float | None
    trust_score: int
    trust_breakdown: list[TrustBreakdownItem]
    specialty_tags: list[str]
    equipment_tags: list[str]
    raw: dict[str, Any] | None = None
