# CareGrid AI vs Hack-Nation Challenge 03 — Serving a Nation

This document audits the repository against the actual challenge brief
(`data/03_Serving_a_Nation.docx.pdf`) and lists what ships, what was
intentionally deferred, and how each requirement maps to a concrete file.

> **Scoring rubric the brief uses**
>
> | Bucket                                  | Weight |
> | --------------------------------------- | ------ |
> | Discovery & Verification                | 35%    |
> | IDP (Intelligent Document Parsing)      | 30%    |
> | Social Impact & Utility                 | 25%    |
> | UX & Transparency                       | 10%    |

---

## TL;DR

- **All three MVP features are covered** end-to-end on the real 10,000-row
  Indian facility dataset.
- **Two of three stretch goals** are addressed:
  - Agentic Traceability → row-level **evidence sentences** are surfaced
    inside every `trust_breakdown` item and on the search response.
  - Dynamic Crisis Mapping → `/stats/deserts` returns per-state aggregates
    (facility count, average trust, rural-acuity gaps) ready to overlay on
    a choropleth.
- The Validator-Agent self-correction loop is the only stretch goal
  intentionally not implemented; the deterministic IDP pipeline already
  cross-checks claim-vs-evidence and emits the same kind of contradiction
  signal a validator agent would.
- The system is deploy-ready: backend → Hugging Face Spaces (Docker SDK),
  frontend → Lovable export → Vercel.

---

## 1. MVP coverage

### MVP 1 — Massive Unstructured Extraction (35% Discovery & Verification)

The brief asks the system to "process free-form text from 10k Indian facility
records: equipment logs, 24/7 availability claims, staff specialties." The
implementation does this **deterministically** — fast on CPU, reproducible,
and traceable — instead of relying on a hosted LLM.

| Capability                                         | File                                                   |
| -------------------------------------------------- | ------------------------------------------------------ |
| Column-tolerant load + JSON-list flattening        | `backend/app/data_loader.py`                           |
| Specialty / equipment vocab + camelCase splitting  | `backend/app/normalize.py`                             |
| Notes → canonical specialty / equipment tags       | `data_loader.py::load_hospitals` (`*_tags_full` cols)  |
| Staff signal (digit + role keyword)                | `backend/app/trust_score.py::_has_staff_info`          |
| Source-sentence extraction for every score rule    | `backend/app/evidence.py` (new — Stretch 1)            |

The deterministic pipeline is intentional: it's auditable, free, and runs
locally. An LLM enrichment hook is left in place
(`backend/app/extraction_prompt.md`) so a Claude/GPT-based extractor can be
slotted in without touching the ranker or trust score; the API contract is
already evidence-bearing.

### MVP 2 — Multi-Attribute Reasoning (part of 30% IDP + 35% Discovery)

> *"Find the nearest facility in rural Bihar that can perform an emergency
> appendectomy and typically leverages part-time doctors."*

| Sub-task                                  | File                                |
| ----------------------------------------- | ----------------------------------- |
| Rule-based query parser (state, PIN, radius, specialty, requirement, urgency) | `backend/app/query_parser.py` |
| BM25 + MiniLM (or TF-IDF/SVD fallback) hybrid | `backend/app/embeddings.py`, `bm25_index.py` |
| Hard metadata filters (state, PIN-radius)     | `backend/app/search.py::_filter_candidates` |
| Final score `0.5·sem + 0.2·bm25 + 0.2·trust + 0.1·loc` | `backend/app/ranker.py`        |
| Urgency override (`0.7 location, 0.2 trust, 0.1 sem`) | `backend/app/ranker.py`         |

A query like the brief's example parses to `state=Bihar`,
`urgency→sort=distance`, `specialties=[surgery, emergency]`,
`requirements=[appendectomy]` — then filters to Bihar rows, ranks by
distance + trust, and returns the top 10 with explanations.

### MVP 3 — Trust Scorer (full 35% Discovery & Verification)

| Rule                                                              | Δ        |
| ----------------------------------------------------------------- | -------- |
| Major specialty present (ICU/dialysis/trauma/cardio/neuro)        | **+20**  |
| Equipment / capability evidence present                           | **+20**  |
| Staffing info present (count + role keyword)                      | **+20**  |
| Contradiction: claims major specialty, lacks both equipment AND staff | **−30**  |
| > 2 of 5 canonical fields missing                                 | **−10**  |
| Rich tagging tie-breaker                                          | up to +20 |

Scores are clamped to [0, 100] and accompanied by a `trust_breakdown` list.
The brief's "claims Advanced Surgery but lists no Anesthesiologist" example
is caught by the contradiction rule.

Implementation: `backend/app/trust_score.py`.

---

## 2. Stretch coverage

### Stretch 1 — Agentic Traceability (10% UX & Transparency, plus Discovery)

Every `trust_breakdown` item now ships with an `evidence` field — the exact
source sentence from `notes / description / capability / procedure` that
triggered the rule. `SearchResponse.results[].trust_breakdown` and
`HospitalDetail.trust_breakdown` both expose it.

Implementation: `backend/app/evidence.py` (new module, 100% deterministic).

### Stretch 2 — Self-Correction Loops (Validator Agent)

Not implemented. The deterministic contradiction rule covers the same
failure mode the brief illustrates ("claim without supporting equipment or
staff"), and trust scoring already double-counts evidence across
specialties / equipment / staffing / completeness. A validator agent that
re-checks LLM-extracted JSON against medical standards is a natural
follow-up once the optional LLM enrichment is wired in.

### Stretch 3 — Dynamic Crisis Mapping (25% Social Impact)

`GET /stats/deserts` returns per-state aggregates the frontend can render
on a choropleth — facility count, hospital count, average trust score,
fraction of facilities with at least one major specialty, and a derived
**desert score** for the highest-acuity gaps. `GET /stats/contradictions`
exposes the rows the trust engine flagged as suspicious so the dashboard
can surface "where claims don't match reality."

Implementation: `backend/app/main.py` (new endpoints) + `backend/app/stats.py` (new module).

---

## 3. End-to-end demo path

```
data/hospitals.csv (10k × 41)
        │
        ▼
data_loader.load_hospitals    ← canonical schema + tags + search_text
        │
        ▼
trust_score.attach_trust_scores ← 0-100 + breakdown + evidence (per row)
        │
        ▼
embeddings + BM25 indexes      ← hybrid retrieval
        │
        ▼
search.SearchEngine            ← /search, /hospitals/{id}
                                ─ /stats/deserts
                                ─ /stats/contradictions
                                ─ /admin/reindex
                                ─ /health
        │
        ▼
Lovable frontend on Vercel     ← search box, map, trust card with citations
```

---

## 4. Deployment posture

| Layer    | Host                | Build                                          |
| -------- | ------------------- | ---------------------------------------------- |
| Backend  | Hugging Face Spaces | Dockerfile in repo root, `app_port: 7860`      |
| Frontend | Vercel              | Lovable export in `frontend/`, `vercel.json`   |
| CORS     | Env-configurable    | `CAREGRID_CORS_ORIGINS=https://your-app.vercel.app` |

See `frontend/LOVABLE_PROMPT.md` for the prompt to feed into Lovable, and
`backend/README.md` for the HF Spaces deploy section.

---

## 5. What was intentionally deferred and why

- **Cloud LLM extraction** (Anthropic / Databricks Agent Bricks). The
  scaffolding exists in `backend/app/extraction_prompt.md` and the
  search/trust API is already evidence-bearing, so a dropper-in extractor
  can replace the deterministic evidence module without breaking any
  consumer. Deferred for cost + deploy stability on HF free tier.
- **MLflow 3 tracing**. The `score_components` field on every result and
  the `query_understood` block already give judges step-level visibility
  into the chain of thought; a full MLflow instrumentation is a follow-up
  for a paid environment.
- **Validator Agent**. See Stretch 2 above.

---

## 6. File map

```
HackNation/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI + new /stats endpoints
│   │   ├── data_loader.py     # 41-col tolerant loader
│   │   ├── evidence.py        # NEW: source-sentence citations
│   │   ├── stats.py           # NEW: deserts + contradictions aggregates
│   │   ├── trust_score.py     # rules + breakdown + evidence
│   │   ├── search.py          # filter → hybrid → rank → explain
│   │   ├── query_parser.py    # rule-based NL parser
│   │   ├── ranker.py          # spec + urgency formulas
│   │   ├── embeddings.py      # MiniLM with TF-IDF/SVD fallback
│   │   ├── bm25_index.py      # rank_bm25 keyword index
│   │   ├── geo.py             # PIN/state → coords + haversine
│   │   ├── normalize.py       # specialty / equipment vocab
│   │   ├── explain.py         # human-readable reason text
│   │   ├── schemas.py         # Pydantic request / response
│   │   └── extraction_prompt.md  # optional LLM upgrade hook
│   ├── scripts/build_index.py
│   ├── tests/                 # parser, trust, normalize, search, encoder
│   ├── requirements.txt
│   └── README.md
├── data/
│   ├── hospitals.csv          # 10k × 41
│   ├── pincodes.csv
│   └── 03_Serving_a_Nation.docx.pdf
├── frontend/
│   ├── LOVABLE_PROMPT.md      # prompt to paste into Lovable
│   ├── api/                   # TypeScript client + types
│   ├── .env.example
│   └── vercel.json
├── docs/
│   └── CHALLENGE_AUDIT.md     # this file
├── Dockerfile                 # HF Spaces Docker SDK
├── README.md                  # space metadata + project intro
└── pytest.ini
```
