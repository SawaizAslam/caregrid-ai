---
title: CareGrid AI Backend
emoji: 🏥
colorFrom: indigo
colorTo: red
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Hybrid search + trust scoring over 10k hospitals.
---

# CareGrid AI

> An Agentic Healthcare Intelligence layer for the Hack-Nation
> *"Serving a Nation"* challenge. Hybrid retrieval over 10,000 messy
> Indian facility records, with a transparent trust scorer that cites the
> exact sentence in each hospital's notes.

This repository hosts:

- **Backend** (`backend/`) — FastAPI service with hybrid search
  (BM25 + MiniLM/FAISS), a rule-based trust scorer, evidence citations,
  and aggregate endpoints for medical-desert mapping. Deploys to
  Hugging Face Spaces via the Docker SDK.
- **Frontend** (`frontend/`) — Lovable.dev export targeting Vercel. The
  Lovable prompt and the TypeScript API client live there.
- **Docs** (`docs/`) — challenge-vs-build audit
  (`docs/CHALLENGE_AUDIT.md`).

## How it maps to the challenge brief

| Brief requirement                                        | Where                                            |
| -------------------------------------------------------- | ------------------------------------------------ |
| MVP1 — Massive Unstructured Extraction                   | `backend/app/data_loader.py`, `normalize.py`     |
| MVP2 — Multi-Attribute Reasoning                         | `backend/app/query_parser.py`, `search.py`       |
| MVP3 — Trust Scorer (with contradiction rule)            | `backend/app/trust_score.py`                     |
| Stretch — Agentic Traceability (row-level citations)     | `backend/app/evidence.py` + `trust_score.py`     |
| Stretch — Dynamic Crisis Mapping                         | `backend/app/stats.py` + `/stats/*` endpoints    |

Full audit: [`docs/CHALLENGE_AUDIT.md`](docs/CHALLENGE_AUDIT.md).
Backend docs: [`backend/README.md`](backend/README.md).

## Local quick start

```bash
python -m venv .venv && .venv\Scripts\Activate.ps1  # macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
python -m backend.scripts.build_index
uvicorn backend.app.main:app --reload --port 8000
# open http://localhost:8000/docs
```

## Deployment

This single repo deploys to **two** services. The frontend talks to the
backend over HTTPS, with an env var controlling the backend URL.

### 1. Backend → Hugging Face Spaces (Docker SDK)

Full step-by-step runbook (auth, push, build logs, env vars, common
issues): [`docs/DEPLOY_HUGGINGFACE.md`](docs/DEPLOY_HUGGINGFACE.md).

TL;DR:

```bash
# 1. Create a new Space (Docker SDK) on huggingface.co.
# 2. Add it as a remote and push the repo:
git remote add space https://huggingface.co/spaces/<you>/caregrid-ai
git push -u space main
```

The `Dockerfile` and the YAML frontmatter at the top of this README do
the rest (pip install, MiniLM prefetch, FAISS/BM25 index pre-build,
uvicorn on port 7860). First build takes ~10 minutes; subsequent pushes
finish in 2–4 minutes via Docker layer cache.

After the first deploy, set `CAREGRID_CORS_ORIGINS` in
**Space → Settings → Variables** to your Vercel URL and **Restart** the
Space.

### 2. Frontend → Lovable → Vercel

The Lovable prompt + a working API client are in
[`frontend/`](frontend/). Workflow:

1. Open [lovable.dev](https://lovable.dev) and paste
   `frontend/LOVABLE_PROMPT.md`.
2. When Lovable asks for the backend URL, give it your HF Space URL.
3. Once the project is generated, click **Connect to GitHub** and let
   Lovable push to a new repo (or paste the generated code on top of
   `frontend/`).
4. Import that repo into Vercel — `vercel.json` is already in
   `frontend/`. Set `VITE_API_URL` (or `NEXT_PUBLIC_API_URL`,
   depending on which framework Lovable picked) to your HF Space URL
   in Vercel → Project Settings → Environment Variables.
5. Deploy. The Vercel domain you receive is what you put back in
   `CAREGRID_CORS_ORIGINS` on the HF Space.

That's the loop. See [`frontend/LOVABLE_PROMPT.md`](frontend/LOVABLE_PROMPT.md)
for the full prompt and the API contract Lovable will be coding against.

## Repo layout

```
HackNation/
├── backend/              # FastAPI app + scripts + tests
├── data/                 # 10k facility CSV + pincodes + challenge PDF
├── docs/                 # CHALLENGE_AUDIT.md
├── frontend/             # Lovable prompt + API client + Vercel config
├── Dockerfile            # HF Spaces image
└── README.md             # this file (also Space landing page)
```
