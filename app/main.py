from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, documents, jobs, questions
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette import status
from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine
from app.services.cache_service import redis
import logging
import asyncio
import time
from contextlib import asynccontextmanager

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.warmed_up = False

    async def _async_warmup():
        start = time.perf_counter()
        logger.info("[WARMUP] Starting comprehensive background warm-up...")
        try:
            # 1. Warm up database connection
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

            # 2. Warm up embedding model
            from app.services.ingestion_service import embed
            await asyncio.to_thread(embed, ["system warm-up query"], is_query=True)

            # 3. Warm up reranker model + dummy rerank
            from app.services.reranker_service import warm_up_reranker, rerank
            await asyncio.to_thread(warm_up_reranker)
            from app.models.chunk import Chunk
            from app.models.page import Page
            dummy_chunk = Chunk(id=0, content="Warmup content verification.", chunk_type="text")
            dummy_page = Page(id=0, page_number=1)
            await asyncio.to_thread(rerank, "warmup query", [(dummy_chunk, dummy_page)], 1)

            elapsed = time.perf_counter() - start
            app.state.warmed_up = True
            logger.info("[WARMUP] Background warm-up completed in %.2fs (DB, embedding, reranker ready)", elapsed)
        except Exception as exc:
            logger.warning("[WARMUP] Background warm-up non-fatal error: %s", exc)
            app.state.warmed_up = True

    app.state.warmup_task = asyncio.create_task(_async_warmup())
    yield


app = FastAPI(title="RAG Document QnA Backend", lifespan=lifespan)

if settings.environment.lower() == "production" and settings.secret_key == "change-me":
    raise RuntimeError("SECRET_KEY must be set to a strong value in production")

app.add_middleware(
    CORSMiddleware,
    # Explicit origins from the deployed Streamlit frontend domain(s).
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

@app.get("/", tags=["system"])
async def root():
    """Redirect root requests to the React frontend UI."""
    target = settings.redirect_base_url or "http://localhost:5173"
    return RedirectResponse(target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@app.get("/health", tags=["system"])
async def health_check():
    """Liveness probe used by the host platform."""
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
async def readiness_check():
    """Readiness probe verifying the dependencies and model warm-up status."""
    dependencies = {"database": "ok", "redis": "ok"}
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed while connecting to PostgreSQL")
        dependencies["database"] = "unavailable"

    try:
        await redis.ping()
    except Exception:
        logger.exception("Readiness check failed while connecting to Redis")
        dependencies["redis"] = "unavailable"

    warmed_up = getattr(app.state, "warmed_up", False)

    if "unavailable" in dependencies.values():
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "warmed_up": warmed_up, "dependencies": dependencies},
        )
    return {
        "status": "ready" if warmed_up else "warming_up",
        "warmed_up": warmed_up,
        "dependencies": dependencies,
    }

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(questions.router, prefix="/questions", tags=["questions"])
