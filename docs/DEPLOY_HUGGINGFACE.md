# Deploying the CareGrid AI Backend to Hugging Face Spaces

Step-by-step guide for shipping `backend/` to a public Hugging Face Space
using the Docker SDK. The repo is already configured — this doc is the
runbook.

---

## What you'll get

A live URL like `https://<you>-caregrid-ai.hf.space` exposing every
backend endpoint:

| Endpoint                       | Purpose                                       |
| ------------------------------ | --------------------------------------------- |
| `GET  /health`                 | Status badge, model in use, dataset rows      |
| `POST /search`                 | NL query → ranked results with citations      |
| `GET  /hospitals/{id}`         | Full record + trust breakdown                 |
| `GET  /stats/overview`         | Dataset counts + facility-type breakdown      |
| `GET  /stats/deserts`          | Per-state desert score (drives the choropleth) |
| `GET  /stats/specialty-gaps`   | Coverage matrix per major specialty           |
| `GET  /stats/contradictions`   | Flagged rows with citation evidence           |
| `GET  /docs`                   | Swagger UI                                    |
| `POST /admin/reindex`          | Rebuild indexes after a dataset swap          |

---

## Prerequisites

1. A free Hugging Face account → https://huggingface.co/join
2. Git installed locally and configured with your HF email.
3. **Optional:** [Git LFS](https://git-lfs.com) — the 10 MB
   `data/hospitals.csv` is small enough to commit normally, but if you
   later add larger files (full PIN dataset, raw notes dumps, model
   checkpoints) you'll want LFS.

---

## Step 1 — Create the Space (one-time)

1. Go to https://huggingface.co/new-space.
2. Fill in:
   - **Owner**: your username (or an org).
   - **Space name**: `caregrid-ai` (or anything you like).
   - **License**: MIT.
   - **Select the Space SDK**: **Docker** → **Blank**.
   - **Space hardware**: `CPU basic · 2 vCPU · 16 GB` (free tier is fine;
     MiniLM + FAISS comfortably fit).
   - **Public** is recommended so the Vercel frontend can hit it without
     auth.
3. Click **Create Space**.

You'll land on an empty Space page with a "Files and versions" tab
containing only `README.md`.

---

## Step 2 — Authenticate git for HF

Hugging Face accepts either a write token (preferred) or SSH.

### Option A — token over HTTPS (easiest)

1. Open https://huggingface.co/settings/tokens → **New token** →
   **Write** scope. Copy the token.
2. Configure git on your machine:

   ```powershell
   git config --global credential.helper manager
   ```

   When git prompts for credentials on first push, enter your HF
   **username** and the **token** as the password. Manager caches it.

### Option B — SSH

```powershell
ssh-keygen -t ed25519 -C "your-email@example.com"
# paste ~/.ssh/id_ed25519.pub at https://huggingface.co/settings/keys
```

Use the SSH URL `git@hf.co:spaces/<you>/caregrid-ai` instead of HTTPS in
Step 4.

---

## Step 3 — Verify the repo is deploy-ready (sanity check)

From `d:\HackNation`:

```powershell
# All tests should pass.
python -m pytest backend/tests -q

# These four files must exist - they drive the Space build.
Test-Path Dockerfile           # True
Test-Path README.md            # True (must contain HF YAML frontmatter)
Test-Path data\hospitals.csv   # True (~10 MB)
Test-Path backend\requirements.txt  # True

# Confirm the dataset isn't gitignored.
git check-ignore data/hospitals.csv
# (should print nothing - meaning git WILL track it)
```

If `check-ignore` echoes the path, your `.gitignore` still excludes the
dataset and the Space won't be able to find it; fix `.gitignore` first.

The root `README.md` already has the YAML frontmatter HF needs:

```yaml
---
title: CareGrid AI Backend
colorFrom: indigo
colorTo: red
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Hybrid search and trust scoring over 10k Indian hospital records.
---
```

Don't remove it. (HF Spaces accepts an optional `emoji:` field as a
single-character icon; we omit it intentionally to keep the README
emoji-free. Add it back if you want a custom Space card icon.)

---

## Step 4 — Push to the Space

Add the Space as a git remote and push.

```powershell
cd d:\HackNation

# If this is a fresh repo:
git init
git add .
git commit -m "Initial commit: CareGrid AI backend"

# If you already have a repo, just commit any pending edits.

# Replace <you> with your HF username.
git remote add space https://huggingface.co/spaces/<you>/caregrid-ai

# First push (tracks 'main' on the Space remote).
git push -u space main
```

If the Space was created with an initial README and your local main
diverges, force-push the first time:

```powershell
git push -u space main --force
```

---

## Step 5 — Watch the build

1. Go to your Space page → **Logs** tab (or **App** → click the gear
   icon → **Logs**).
2. You'll see Docker pulling Python 3.11-slim, installing
   `backend/requirements.txt`, copying the dataset, prefetching MiniLM
   weights, and finally running `python -m backend.scripts.build_index`.
3. First build takes **8–15 minutes**:
   - ~3 min for pip install (sentence-transformers + torch are the slow
     ones).
   - ~2 min for the MiniLM model download.
   - ~3 min for the index build over 10k rows on CPU basic.
4. When the log ends with:

   ```
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://0.0.0.0:7860
   ```

   the Space is **live**.

5. Confirm:

   ```powershell
   curl https://<you>-caregrid-ai.hf.space/health
   ```

   You should get something like:

   ```json
   {
     "status": "ok",
     "dataset_rows": 10000,
     "faiss_loaded": true,
     "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
     "index_path": "/app/data/index/faiss.index",
     "pincodes_loaded": 86
   }
   ```

---

## Step 6 — Configure environment variables

Space → **Settings** → **Variables and secrets** → **New variable**.

| Variable                 | Required? | Value                                                          |
| ------------------------ | --------- | -------------------------------------------------------------- |
| `CAREGRID_CORS_ORIGINS`  | yes       | `https://<your-app>.vercel.app,http://localhost:5173`          |
| `CAREGRID_ENCODER`       | no        | omit for auto-select; force fallback with `tfidf` if MiniLM fails |
| `PORT`                   | no        | leave at default `7860`                                        |
| `CAREGRID_DATA_DIR`      | no        | leave at `/app/data` (set by the Dockerfile)                   |

`CAREGRID_CORS_ORIGINS` is the only one you'll definitely set — the
backend defaults to `*` for first-deploy convenience but tightening it
to your real Vercel URL is a 30-second hardening win. After saving,
click **Restart** on the Space so the new env var takes effect.

---

## Step 7 — Smoke-test the live API

```powershell
$BASE = "https://<you>-caregrid-ai.hf.space"

curl "$BASE/health"
curl "$BASE/stats/overview"
curl "$BASE/stats/deserts?top_n=5"

curl -X POST "$BASE/search" `
  -H "Content-Type: application/json" `
  -d '{"query":"nearest ICU hospital in Bihar with oxygen"}'
```

Each `trust_breakdown` item in the search response should now include
an `evidence` field with the source sentence — that's the citation
layer judges look for.

---

## Updating after code changes

Standard git flow:

```powershell
cd d:\HackNation
git add .
git commit -m "Refine trust score weights"
git push space main
```

The Space auto-rebuilds. Watch the **Logs** tab; subsequent builds use
Docker's layer cache and finish in **2–4 minutes** because pip and the
model download are cached.

If you only changed code (not `requirements.txt` or `data/`), Docker
re-uses cached layers up to the `COPY backend /app/backend` step.

---

## Updating the dataset

1. Replace `data/hospitals.csv` (or `.xlsx`) locally.
2. Commit + push.
3. The Dockerfile re-runs `python -m backend.scripts.build_index`
   during build, so the new index is baked in.

Alternative (faster, no rebuild):

1. Upload the new file via the Space's **Files** tab.
2. Hit `POST /admin/reindex` against the live URL — that rebuilds
   indexes in-process and swaps them in.

---

## Common issues

### Build fails: `Killed` during pip install

Pip ran out of RAM. Either:
- Bump the Space hardware to **CPU upgrade** (still free for short
  bursts), **or**
- Add `pip install --no-cache-dir --no-build-isolation` to the
  Dockerfile.

### MiniLM download times out during build

The Dockerfile already wraps the prefetch in `|| echo "..."` so the
build keeps going; the model will lazy-load on first request instead.
If you want a guaranteed-fresh prefetch, restart the Space.

### `503 Search engine not initialized`

The lifespan event errored — check **Logs** for the traceback. Most
common cause: `data/hospitals.csv` missing from the image. Fix:
`git ls-files data/hospitals.csv` should print the path; if it doesn't,
your `.gitignore` is still excluding it.

### CORS error from the Vercel frontend

Open browser DevTools → Network → look at the failed `/search` request:

- If the response is `403` or has no `Access-Control-Allow-Origin`
  header, your `CAREGRID_CORS_ORIGINS` doesn't include the calling
  origin. Add it (comma-separated, no trailing slash) and **Restart**
  the Space.
- If the response is `503`, it's the engine error above — fix that
  first; CORS is fine.

### Space sleeps and the first request takes 30 s

Free-tier Spaces sleep after ~48 h of inactivity. The wake-up cycle
loads the FAISS index from disk (~5 s) and re-imports the encoder
(~10 s). Subsequent requests are fast. To keep it warm, hit
`/health` from a Vercel cron or an uptime monitor every few hours.

### `404 Not Found` for the Space URL

The Space is private. Either flip it to **Public** in
**Settings → Visibility**, or add an Authorization header with an HF
token to every request from your frontend.

---

## Quick reference

```text
Space URL      https://<you>-caregrid-ai.hf.space
SDK            docker
Port           7860 (set by README YAML + Dockerfile)
Free tier      2 vCPU, 16 GB RAM, sleeps after inactivity
Restart        Space page -> Settings -> Restart this Space
Rebuild        git push space main  (or Settings -> Factory rebuild)
Logs           Space page -> Logs tab
Live shell     Space page -> Settings -> Open a terminal
```

That's the whole pipeline. Push, wait ~10 minutes, set CORS, and your
backend is live.
