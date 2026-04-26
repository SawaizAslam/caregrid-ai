"""FastAPI entry point for CareGrid AI."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import (
    CORS_ORIGINS,
    EMBEDDING_MODEL,
    FAISS_INDEX_PATH,
    PINCODES_PATH,
    ensure_dirs,
)
from .embeddings import get_encoder
from .geo import get_geo_index
from .schemas import (
    HealthResponse,
    HospitalDetail,
    SearchRequest,
    SearchResponse,
)
from .search import SearchEngine
from .stats import (
    flagged_contradictions,
    overview,
    specialty_gaps,
    state_deserts,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    logger.info("Starting CareGrid AI backend...")
    try:
        engine = SearchEngine.from_disk_or_build()
        app.state.engine = engine
        logger.info("Engine ready: %d hospitals indexed.", len(engine.df))
    except FileNotFoundError as exc:
        logger.error("Startup failed: %s", exc)
        # Don't crash the process - /health will reflect the broken state and the
        # user can drop the dataset in and hit POST /admin/reindex.
        app.state.engine = None
        app.state.startup_error = str(exc)
    yield
    logger.info("Shutting down CareGrid AI backend.")


app = FastAPI(
    title="CareGrid AI",
    description="AI-powered healthcare intelligence: hybrid search over Indian hospitals.",
    version="0.1.0",
    lifespan=lifespan,
)

# Browsers reject "Access-Control-Allow-Origin: *" together with
# `allow_credentials=true`. Disable credentials when the wildcard is used so
# the public Hugging Face Space can serve any frontend.
_origins = [o.strip() for o in CORS_ORIGINS if o and o.strip()]
_allow_credentials = not (len(_origins) == 1 and _origins[0] == "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _engine(app: FastAPI) -> SearchEngine:
    engine = getattr(app.state, "engine", None)
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail=getattr(app.state, "startup_error", "Search engine not initialized."),
        )
    return engine


@app.get("/health", response_model=HealthResponse)
def health():
    engine = getattr(app.state, "engine", None)
    try:
        pin_rows = len(get_geo_index().pins)
    except Exception:  # noqa: BLE001
        pin_rows = 0
    try:
        active_encoder = get_encoder().name
    except Exception:  # noqa: BLE001
        active_encoder = EMBEDDING_MODEL
    return HealthResponse(
        status="ok" if engine is not None else "degraded",
        dataset_rows=len(engine.df) if engine is not None else 0,
        faiss_loaded=engine is not None and engine.faiss_index is not None,
        embedding_model=active_encoder,
        index_path=str(FAISS_INDEX_PATH),
        pincodes_loaded=pin_rows,
    )


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    engine = _engine(app)
    payload = engine.search(req.query, top_k=req.top_k)
    return SearchResponse(**payload)


@app.get("/hospitals/{hospital_id}", response_model=HospitalDetail)
def get_hospital(hospital_id: int):
    engine = _engine(app)
    row = engine.get_hospital(hospital_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Hospital {hospital_id} not found")
    return HospitalDetail(
        hospital_id=int(row.get("hospital_id", hospital_id)),
        hospital_name=row.get("hospital_name", ""),
        state=row.get("state") or None,
        district=row.get("district") or None,
        pin_code=row.get("pin_code") or None,
        address=row.get("address") or None,
        specialties=row.get("specialties") or None,
        equipment=row.get("equipment") or None,
        notes=row.get("notes") or None,
        staff=row.get("staff") or None,
        phone=row.get("phone") or None,
        latitude=row.get("latitude"),
        longitude=row.get("longitude"),
        trust_score=int(row.get("trust_score", 0)),
        trust_breakdown=row.get("trust_breakdown", []),
        specialty_tags=row.get("specialty_tags", []),
        equipment_tags=row.get("equipment_tags", []),
    )


@app.post("/admin/reindex")
def reindex():
    """Force a fresh build of every index. Useful after dropping a new dataset in."""
    ensure_dirs()
    engine = SearchEngine.build()
    engine.persist()
    app.state.engine = engine
    return {"status": "ok", "dataset_rows": len(engine.df)}


@app.get("/stats/overview")
def stats_overview():
    """Top-line counts the dashboard shows above the map."""
    engine = _engine(app)
    return overview(engine.df)


@app.get("/stats/deserts")
def stats_deserts(top_n: int = 36):
    """Per-state aggregates ranked by desert score (higher = worse).

    Drives the choropleth on the dashboard. Each row carries facility_count,
    avg_trust_score, hospital_share, major_specialty_share, and a derived
    desert_score in [0, 1].
    """
    engine = _engine(app)
    return {"states": state_deserts(engine.df, top_n=top_n)}


@app.get("/stats/specialty-gaps")
def stats_specialty_gaps():
    """For every major specialty, count facilities and rank states by coverage."""
    engine = _engine(app)
    return {"specialties": specialty_gaps(engine.df)}


@app.get("/stats/contradictions")
def stats_contradictions(limit: int = 50):
    """Hospitals whose trust score flagged a Contradiction rule, with citations."""
    engine = _engine(app)
    return {"flagged": flagged_contradictions(engine.df, limit=limit)}


@app.get("/")
def root():
    return {
        "name": "CareGrid AI",
        "endpoints": [
            "/health",
            "/search (POST)",
            "/hospitals/{id}",
            "/stats/overview",
            "/stats/deserts",
            "/stats/specialty-gaps",
            "/stats/contradictions",
            "/admin/reindex (POST)",
        ],
        "docs": "/docs",
    }
