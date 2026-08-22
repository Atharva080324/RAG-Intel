# Railway Deployment Guide

This guide deploys the RAG API + Celery worker on **Railway** using the free
$5 trial credits. **No credit card is needed for the initial trial** — once the
trial expires the services pause until you add a card.

## Architecture

- **Railway** hosts **2 services** that share the same Docker image:
  1. `rag-api` — FastAPI web server (port $PORT)
  2. `rag-worker` — Celery worker (consumes from Redis)
- **Neon** — managed PostgreSQL with pgvector (free tier, already configured)
- **Upstash** — managed Redis (free tier, already configured)
- **Streamlit** — deployed separately on Streamlit Community Cloud (free)

This avoids Railway's PostgreSQL/Redis charges (which would exceed the $5
credit), so all $5 lasts ~12–15 days of intermittent dev/testing usage.

## Quick Deploy

### 1. Push to GitHub
```bash
git add .
git commit -m "Railway-optimized Dockerfile: dynamic PORT, supervisord"
git push origin main
```

### 2. Create Railway project
1. Go to https://railway.app → **New Project** → **Deploy from GitHub repo**
2. Select your `rag-document-intelligence` repository
3. Railway auto-detects the `Dockerfile` and builds it

### 3. Add 2 services
In the Railway dashboard, click **"Add Service"** twice:

**Service 1 — `rag-api` (Web):**
- Type: Web Service
- Start Command: `sh start.sh`
- Port: `$PORT` (auto-detected by Railway)
- Environment: `production`

**Service 2 — `rag-worker` (Worker):**
- Type: Worker
- Start Command: `celery -A app.workers.celery_app worker --loglevel=info`
- Environment: `production`

### 4. Configure environment variables
Copy **all** variables from your local `.env` into the Railway dashboard:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon connection string |
| `REDIS_URL` | Upstash connection string |
| `CELERY_BROKER_URL` | Same as `REDIS_URL` |
| `CELERY_RESULT_BACKEND` | Same as `REDIS_URL` |
| `SECRET_KEY` | Your secret key |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |
| `ALGORITHM` | `HS256` |
| `PGVECTOR_EXTENSION` | `vector` |
| `MAX_UPLOAD_SIZE_BYTES` | `10485760` |
| `ALLOWED_UPLOAD_EXTENSIONS` | `pdf,txt,md` |
| `ENVIRONMENT` | `production` |
| `HF_TOKEN` | Your HF token |
| `HF_HOME` | `/tmp/huggingface` |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` |
| `EMBEDDING_DIMENSION` | `384` |
| `EMBEDDING_BATCH_SIZE` | `32` |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L6-v2` |
| `GROQ_API_KEY` | Your Groq key |
| `GROQ_MODEL` | `openai/gpt-oss-120b` |
| `GOOGLE_CLIENT_ID` | Your Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Your Google OAuth secret |
| `GOOGLE_REDIRECT_URI` | `https://<your-railway-subdomain>/auth/google/callback` |
| `STORAGE_BACKEND` | `postgres` |
| `CORS_ORIGINS` | `https://<your-streamlit-url>` (add Streamlit URL after step 5) |

### 5. Set up Streamlit frontend (free, separate)
1. Go to https://share.streamlit.io → **New app**
2. Connect your GitHub repo, select `app/streamlit_app.py`
3. In `.streamlit/secrets.toml`:
   ```toml
   API_BASE = "https://<your-railway-subdomain>"
   ```
4. Copy the Streamlit URL into Railway's `CORS_ORIGINS` and
   `STREAMLIT_FRONTEND_URL` env vars.

### 6. Deploy
Both services will auto-build and deploy from the Dockerfile. The `web`
service exposes the FastAPI on `$PORT`; the `worker` runs Celery.

### 7. Verify
```
curl https://<your-rag-api>.railway.app/health
# Expected: {"status":"ok"}
```

## Notes
- The `web` service runs `sh start.sh`, which calls `alembic upgrade head`
  (migrations) **then** starts uvicorn + the worker via supervisord — so even
  a single web service handles both API and worker. If you prefer separate
  services, use the two-service setup in Step 3 instead.
- The `STORAGE_BACKEND=postgres` setting stores uploaded files as bytea blobs
  in Neon — **no object storage / card / billing required**.