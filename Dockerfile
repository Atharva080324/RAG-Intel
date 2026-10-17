# syntax=docker/dockerfile:1
# ──────────────────────────────────────────────────────────────────────────────
# Multi-stage Dockerfile for the RAG Document Intelligence API + Celery worker.
#
# Targets linux/arm64 (Oracle Cloud A1 / Ampere) but also builds on amd64
# because python:3.12-slim has both native images.
#
# Usage:
#   docker build --target=runtime -t rag-app:latest .
#   # API:    docker run -e ... rag-app uvicorn app.main:app --host 0.0.0.0 --port 8000
#   # Worker: docker run -e ... rag-app celery -A app.workers.celery_app worker --loglevel=info
# ──────────────────────────────────────────────────────────────────────────────

# ── Stage 1: deps ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS deps

# System packages needed at build time only
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="RAG Document Intelligence"
LABEL org.opencontainers.image.description="FastAPI + Celery RAG backend"

# Runtime system packages (Tesseract for OCR, libpq for asyncpg native fallback)
RUN apt-get update && apt-get install -y --no-install-recommends \
        # Tesseract OCR — needed by ingestion_service.py for scanned PDFs
        tesseract-ocr \
        tesseract-ocr-eng \
        # libpq shared library for asyncpg
        libpq5 \
        # curl is used by the keepalive script and Docker healthchecks
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from the build stage
COPY --from=deps /install /usr/local

# Create a non-root user for principle of least privilege
RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app

# Copy application code (order: less-changed files first for layer cache)
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY app/ ./app/
COPY src/ ./src/
COPY scripts/ ./scripts/

# Hugging Face cache inside the container (avoids writing to /root)
ENV HF_HOME=/app/.cache/huggingface
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Pre-download default embedding and reranker models at build time so the container
# starts warm with zero cold-download delays and zero external network dependency.
RUN mkdir -p /app/.cache/huggingface && \
    python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; SentenceTransformer('BAAI/bge-small-en-v1.5'); CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2')" && \
    chown -R app:app /app

# The container listens on 8000; Caddy is the only public TLS terminator.
EXPOSE 8000

# Switch to non-root user
USER app

# Default command = API server.
# 2 workers suit the 2 OCPU ARM target (matches physical cores without RAM bloat).
# Override for the worker service in docker-compose.prod.yml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

