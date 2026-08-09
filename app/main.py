from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, documents, jobs, questions
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.core.config import settings
import logging

app = FastAPI(title="RAG Document QnA Backend")
logger = logging.getLogger("app")

if settings.environment.lower() == "production" and settings.secret_key == "change-me":
    raise RuntimeError("SECRET_KEY must be set to a strong value in production")

app.add_middleware(
    CORSMiddleware,
    # Configure explicit origins before enabling credentialed browser requests.
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok"}

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(questions.router, prefix="/questions", tags=["questions"])
