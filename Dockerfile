# CareGrid AI — backend image for Hugging Face Spaces (Docker SDK).
#
# Build context is the repo root so we can copy backend/ + data/ in one
# shot. The Space exposes port 7860 (HF default).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    HF_HOME=/tmp/hf \
    TRANSFORMERS_CACHE=/tmp/hf \
    SENTENCE_TRANSFORMERS_HOME=/tmp/hf

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libstdc++6 curl \
 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# App + dataset.
COPY backend /app/backend
COPY data /app/data

# Pre-download the MiniLM weights so the first request isn't slow. We
# tolerate a network error here so the build still succeeds offline.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" \
    || echo "MiniLM prefetch skipped (will lazy-load on first query)"

# Build the FAISS / BM25 / metadata indexes once, baked into the image, so
# the Space boots in seconds instead of minutes.
RUN python -m backend.scripts.build_index || echo "Build index deferred to first boot"

ENV CAREGRID_DATA_DIR=/app/data \
    CAREGRID_CORS_ORIGINS=* \
    PORT=7860

EXPOSE 7860

CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
