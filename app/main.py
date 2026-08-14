from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, documents, jobs, questions
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine
from app.services.cache_service import redis
import logging

app = FastAPI(title="RAG Document QnA Backend")
logger = logging.getLogger("app")

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

@app.get("/health", tags=["system"])
async def health_check():
    """Liveness probe used by the host platform."""
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
async def readiness_check():
    """Readiness probe verifying the dependencies required to serve traffic."""
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

    if "unavailable" in dependencies.values():
        return JSONResponse(status_code=503, content={"status": "unavailable", "dependencies": dependencies})
    return {"status": "ready", "dependencies": dependencies}

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(questions.router, prefix="/questions", tags=["questions"])
