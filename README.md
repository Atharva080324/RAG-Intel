# RAG Document Intelligence Platform

An asynchronous, document-aware Retrieval-Augmented Generation (RAG) backend for uploading PDFs and text documents, querying them with grounded answers, and performing exact calculations over extracted tables.

The project is designed as a production-minded backend rather than a single-document demo. It combines durable ingestion jobs, structured document parsing, hybrid retrieval, corrective workflow orchestration, authentication, and deployment configuration.

## Highlights

- Asynchronous FastAPI API with Celery/Redis background ingestion and job polling
- PDF, TXT, and Markdown upload support with content-hash deduplication
- PDF text extraction with PyMuPDF, table extraction with pdfplumber, and OCR fallback through Tesseract
- Page, text, and table chunks persisted in PostgreSQL with pgvector embeddings and full-text search vectors
- Hybrid retrieval that fuses vector similarity and PostgreSQL lexical search, then reranks candidates with a cross-encoder
- LangGraph corrective-RAG workflow: route, retrieve, grade grounding, rewrite, and retry (up to two times)
- Table analytics path for exact `average`, `sum`, `minimum`, and `maximum` calculations over retrieved Markdown tables
- JWT authentication, password signup/login, and Google OAuth 2.0 authorization-code login
- Per-user document isolation, rate limiting, security headers, upload validation, Docker Compose, and Render Blueprint configuration

## Architecture

```text
Client / Streamlit UI
        |
        v
FastAPI API ── JWT / Google OAuth 2.0
   |                 |
   |                 +── Redis (OAuth state, rate limiting)
   |
   +── Upload -> PostgreSQL job -> Celery worker
   |                              |
   |                              +── parse PDF/text, extract tables/OCR
   |                              +── chunk + embed -> PostgreSQL + pgvector
   |
   +── Question -> LangGraph corrective workflow
                        |
                        +── vector + full-text retrieval -> reranker
                        +── grounded answer with page citations
                        +── table analytics when applicable
```

## Tech stack

| Area | Tools |
| --- | --- |
| API and validation | FastAPI, Pydantic, Uvicorn |
| Persistence | PostgreSQL, SQLAlchemy async, Alembic, pgvector |
| Background work | Celery, Redis |
| Parsing and analytics | PyMuPDF, pdfplumber, Tesseract, pandas |
| Retrieval and orchestration | Hugging Face Inference embeddings, PostgreSQL FTS, cross-encoder reranking, LangGraph |
| Authentication | bcrypt, JWT, Google OAuth 2.0 |
| Operations | Docker Compose, Render, Streamlit test UI |

## Project structure

```text
app/
  routers/       # auth, documents, jobs, and question endpoints
  services/      # parsing, ingestion, retrieval, reranking, analytics, users
  workers/       # Celery application and document-ingestion task
  models/        # users, documents, pages, chunks, jobs
  schemas/       # API request and response contracts
  middleware/    # rate limiting and security headers
  streamlit_app.py
alembic/         # PostgreSQL migrations, including pgvector and Google identity
tests/           # automated API tests
```

## Local setup

### 1. Prerequisites

- Python 3.12+
- PostgreSQL with the `vector` extension
- Redis
- Tesseract (optional, enables OCR fallback for scanned PDFs)
- A Hugging Face access token for hosted embeddings
- A Groq API key for answer generation

### 2. Configure environment

Copy `.env.example` to `.env` and fill in the required values. Do not commit `.env`.

```env
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DB_NAME
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=replace-with-a-long-random-secret
HF_TOKEN=your-hugging-face-token
GROQ_API_KEY=your-groq-api-key
```

For Google login, create a Web Application OAuth client in Google Cloud and add this authorized redirect URI:

```env
GOOGLE_CLIENT_ID=your-google-web-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/auth/google/callback
```

### 3. Install and run

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
alembic upgrade head
py -m uvicorn app.main:app --reload
```

Run the worker separately (Windows requires the `solo` pool):

```powershell
.\.venv\Scripts\Activate.ps1
celery -A app.workers.celery_app worker --pool=solo --loglevel=info
```

Optional local tester UI:

```powershell
streamlit run app/streamlit_app.py
```

The interactive API docs are available at `http://127.0.0.1:8000/docs`.

## API overview

| Endpoint | Purpose |
| --- | --- |
| `POST /auth/signup` | Create an email/password account |
| `POST /auth/token` | Obtain a JWT using OAuth2 password form data |
| `GET /auth/google/login` | Begin Google OAuth sign-in |
| `GET /auth/google/callback` | Complete Google OAuth sign-in |
| `POST /documents/upload` | Upload a PDF, TXT, or Markdown document; returns an ingestion job |
| `GET /documents/` | List the authenticated user's documents |
| `GET /jobs/{job_id}` | Poll ingestion progress and failure details |
| `POST /questions/analyze` | Retrieve evidence, generate an answer, and return citations |
| `GET /health` | Liveness check |

All document and question routes require `Authorization: Bearer <token>`.

## Retrieval workflow

1. Ingestion extracts page text and tables, then stores text and Markdown-table chunks with page metadata.
2. A query is classified as text- or table-oriented.
3. Semantic pgvector search and PostgreSQL full-text search each produce candidate chunks.
4. Reciprocal-rank fusion merges the candidates; a cross-encoder reranks the final shortlist.
5. The LangGraph workflow grades lexical grounding. Weak results trigger a more focused query and a bounded retry.
6. The answer prompt requires source markers such as `[S1]`; numeric table requests can be calculated directly with pandas.

## Deployment

`docker-compose.yml` starts the API, Celery worker, PostgreSQL/pgvector, and Redis. `render.yaml` defines corresponding Render web and worker services for managed PostgreSQL and Redis providers.

Before a production deployment, set all secret environment variables in the host dashboard, set a strong `SECRET_KEY`, configure the production Google redirect URI, and ensure the `vector` extension is available on the database.

## Current implementation status

Implemented: foundation, async ingestion, structured PDF/table parsing, core RAG Q&A, LangGraph corrective retrieval, hybrid search/reranking, table analytics, authentication, and deployment scaffolding.

Planned next: streamed responses, richer metadata filters, broader table operations, evaluation data/metrics, and a deployed public demo.

## Security notes

- `.env`, virtual environments, upload data, and Python caches are excluded by `.gitignore`.
- Never place OAuth client secrets, database URLs, Redis credentials, tokens, or production JWT secrets in Git.
- Google OAuth state is stored in Redis with a 10-minute expiry and consumed after use.


