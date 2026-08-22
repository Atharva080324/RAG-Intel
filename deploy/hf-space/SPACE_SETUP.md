# Card-free deployment: Hugging Face Spaces (backend+worker) + Streamlit Community Cloud (UI)

This guide is **only for the free, no-credit-card deployment**. The repo's `Dockerfile`
now runs **both** the FastAPI server (port 7860) and the Celery worker in **one** container
via `supervisord`, so a single Hugging Face Space hosts both processes. The Streamlit UI is
hosted separately (free, no card) and just calls the Space's API URL.

Neon (Postgres/pgvector + file blobs) and Upstash (Redis) stay exactly as they already are.

---

## Part A — Backend: FastAPI + Celery worker on Hugging Face Spaces

> Files that power this: `Dockerfile` (root), `supervisord.conf`, `start.sh`.
> `start.sh` runs `alembic upgrade head` automatically, then starts uvicorn + celery.

### 1. Create the Space
1. Go to https://huggingface.co and **sign up** (free, **no credit card**).
2. Click your avatar → **New Space**.
   - **Owner**: your username
   - **Space name**: e.g. `rag-api`
   - **SDK**: `Docker`
   - **Hardware**: `CPU basic` (free; select the 2 vCPU option — still free)
   - **Visibility**: `Public`
   - **Create Space**.

### 2. Put this project into the Space
The Space is its own git repo at `https://huggingface.co/spaces/<you>/rag-api`.

Easiest: clone it, copy the repo in, add the Space `README.md`, push.

```bash
git clone https://huggingface.co/spaces/<you>/rag-api
cd rag-api
# copy the files from this project into this folder
copy *.py *.toml *.ini *.sh *.conf Dockerfile requirements.txt  # from the project
xcopy /E app app
xcopy /E alembic alembic
# create the Space README with frontmatter:
```

Add a `README.md` at the **Space root** with this exact header (do NOT edit your project's README):

```markdown
---
title: RAG API
sdk: docker
---
```

Then commit & push. (Alternatively, use the web **"Upload files"** tab to drag the project in.)

### 3. Set secrets on the Space
Space → **Settings** → **Variables and secrets** → add (use “Secret” where noted):

| Key | Value |
|---|---|
| `DATABASE_URL` | your Neon async URL (from `.env`) |
| `REDIS_URL` | your Upstash `rediss://...` URL |
| `CELERY_BROKER_URL` | same Upstash URL |
| `CELERY_RESULT_BACKEND` | same Upstash URL |
| `SECRET_KEY` | your `.env` SECRET_KEY |
| `HF_TOKEN` | your HF token |
| `GROQ_API_KEY` | your Groq key |
| `GOOGLE_CLIENT_ID` | your OAuth client id |
| `GOOGLE_CLIENT_SECRET` | secret |
| `GOOGLE_REDIRECT_URI` | `https://<you>-rag-api.hf.space/auth/google/callback` |
| `ENVIRONMENT` | `production` |
| `STORAGE_BACKEND` | `postgres` |
| `STREAMLIT_FRONTEND_URL` | the Streamlit URL from Part B (e.g. `https://rag.streamlit.app`) |
| `CORS_ORIGINS` | the same Streamlit URL |

### 4. Build & run, then verify
- Save → the Space builds the Docker image and starts. It renders the API at:
  `https://<you>-rag-api.hf.space`
- Verify: open `https://<you>-rag-api.hf.space/health` → `{"status":"ok"}`
- Add the Google callback to your OAuth app (Step 5).

### 5. Google OAuth redirect
In Google Cloud (your existing web client), add:
```
https://<you>-rag-api.hf.space/auth/google/callback
```

---

## Part B — UI: Streamlit app on Streamlit Community Cloud (free, no card)

1. Go to https://share.streamlit.io and **sign in with GitHub** (use the same repo).
2. **Create app** → repo `Atharva080324/rag-document-intelligence` → branch `main` → file `app/streamlit_app.py`.
3. In the app → **Settings → Secrets**, set one secret:
   ```toml
   API_BASE = "https://<you>-rag-api.hf.space"
   ```
4. Deploy → you get a URL like `https://rag.streamlit.app`.
5. Update the Space secret `STREAMLIT_FRONTEND_URL` and `CORS_ORIGINS` to this URL.

---

## Final test
- Open the Streamlit URL → sign in → upload a PDF → job becomes **Completed**
  (proves the worker fetched the bytes from the shared Neon DB) → ask a question.

> Free-tier note: HF Spaces and Neon/Upstash sleep on inactivity; the first request
> after idle may take ~30–60s to wake. Normal for free.