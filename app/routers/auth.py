import asyncio
from datetime import timedelta
from secrets import token_urlsafe
import logging
import uuid

from urllib.parse import urlencode, quote
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.core.dependencies import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.models.user import User
from app.models.document import Document
from app.models.page import Page
from app.models.chunk import Chunk
from app.services.user_service import (
    create_google_user,
    create_user,
    get_user_by_email,
    get_user_by_google_subject,
)
from app.services.cache_service import delete_cache, get_cache, set_cache, redis
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserRead

router = APIRouter()


GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def _google_configured() -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google authentication is not configured")


def _google_login_url(state: str) -> str:
    query = urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    })
    return f"{GOOGLE_AUTHORIZE_URL}?{query}"

@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(user_create: UserCreate, db: AsyncSession = Depends(get_db)):
    existing_user = await get_user_by_email(db, user_create.email)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Unable to create account")
    try:
        user = await create_user(db, user_create)
    except IntegrityError:
        # The pre-check above is only an optimisation; this handles concurrent
        # registrations without exposing a database error.
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Unable to create account")
    return user

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    # OAuth2 uses the field name `username`; this API accepts an email there.
    email = form_data.username.strip().lower()
    user = await get_user_by_email(db, email)
    if not user or not user.is_active or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = await create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.get("/google/login", include_in_schema=True)
async def google_login():
    _google_configured()
    state = token_urlsafe(32)
    await set_cache(f"oauth:google:state:{state}", "1", expire=600)
    return RedirectResponse(_google_login_url(state), status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if error:
        return RedirectResponse(
            f"{settings.redirect_base_url}/?oauth_error={quote(error)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    _google_configured()
    if not code or not state:
        return RedirectResponse(
            f"{settings.redirect_base_url}/?oauth_error=invalid_request",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    state_key = f"oauth:google:state:{state}"
    cached_state = await get_cache(state_key)
    if not cached_state:
        return RedirectResponse(
            f"{settings.redirect_base_url}/?oauth_error=invalid_state",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    await delete_cache(state_key)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_response.is_error:
                raise RuntimeError("Google token exchange failed")
            token_data = token_response.json()
            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {token_data.get('access_token', '')}"},
            )
            if userinfo_response.is_error:
                raise RuntimeError("Google user information request failed")
            profile = userinfo_response.json()
    except Exception:
        return RedirectResponse(
            f"{settings.redirect_base_url}/?oauth_error=oauth_exchange_failed",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    google_subject = profile.get("sub")
    email = profile.get("email", "").strip().lower()
    if not google_subject or not email or profile.get("email_verified") is not True:
        return RedirectResponse(
            f"{settings.redirect_base_url}/?oauth_error=email_not_verified",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    user = await get_user_by_google_subject(db, google_subject)
    if user is None:
        user = await get_user_by_email(db, email)
        if user is None:
            user = await create_google_user(db, email, google_subject)
        else:
            user.google_subject = google_subject
            await db.commit()
            await db.refresh(user)
    if not user.is_active:
        return RedirectResponse(
            f"{settings.redirect_base_url}/?oauth_error=inactive_user",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    access_token = await create_access_token(data={"sub": user.email})
    redirect_target = f"{settings.redirect_base_url}/?token={quote(access_token)}"
    return RedirectResponse(redirect_target, status_code=status.HTTP_303_SEE_OTHER)


logger = logging.getLogger("app.auth")


@router.post(
    "/demo",
    response_model=Token,
    summary="Obtain an isolated demo session JWT (DEMO_MODE only)",
    description=(
        "Returns a short-lived JWT for a fresh isolated demo user with pre-seeded documents. "
        "Only available when **DEMO_MODE=true**."
    ),
)
async def demo_login(request: Request, db: AsyncSession = Depends(get_db)) -> Token:
    """Issue a fresh per-session demo JWT with pre-seeded documents and per-IP rate limiting."""
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo mode is not enabled on this deployment",
        )

    # 1. Per-IP rate limiting (guard against automated abuse)
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    ip_key = f"ratelimit:demo_ip:{client_ip}"
    try:
        current = await redis.incr(ip_key)
        if current == 1:
            await redis.expire(ip_key, 3600)  # 1 hour window
        if current > 30:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demo session creation limit reached for this IP address. Please try again later.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Redis IP rate limit check non-fatal error: %s", exc)

    # 2. Create isolated session demo user
    session_id = uuid.uuid4().hex[:10]
    session_email = f"demo_{session_id}@rag-demo.internal"
    logger.info("Provisioning isolated demo session user %s (client IP: %s)", session_email, client_ip)

    session_user = User(
        email=session_email,
        hashed_password=get_password_hash(settings.demo_user_password),
        is_active=True,
    )
    db.add(session_user)
    await db.commit()
    await db.refresh(session_user)

    # 3. Clone seeded sample documents from master demo user (if master user has documents)
    try:
        master_email = settings.demo_user_email.strip().lower()
        master_user = await get_user_by_email(db, master_email)
        if master_user:
            res = await db.execute(
                select(Document).where(Document.user_id == master_user.id, Document.status == "completed")
            )
            master_docs = res.scalars().all() if hasattr(res, "scalars") and not asyncio.iscoroutinefunction(res.scalars) else []

            for mdoc in master_docs:
                new_doc = Document(
                    user_id=session_user.id,
                    filename=mdoc.filename,
                    content_hash=mdoc.content_hash,
                    status="completed",
                    source_path=mdoc.source_path,
                )
                db.add(new_doc)
                await db.flush()

                # Copy pages
                p_res = await db.execute(select(Page).where(Page.document_id == mdoc.id))
                mpages = p_res.scalars().all() if hasattr(p_res, "scalars") else []
                page_map = {}
                for mp in mpages:
                    np = Page(
                        document_id=new_doc.id,
                        page_number=mp.page_number,
                        page_text=mp.page_text,
                    )
                    db.add(np)
                    await db.flush()
                    page_map[mp.id] = np.id

                # Copy chunks
                c_res = await db.execute(select(Chunk).where(Chunk.document_id == mdoc.id))
                mchunks = c_res.scalars().all() if hasattr(c_res, "scalars") else []
                for mc in mchunks:
                    nc = Chunk(
                        document_id=new_doc.id,
                        page_id=page_map.get(mc.page_id),
                        chunk_type=mc.chunk_type,
                        content=mc.content,
                        chunk_metadata=mc.chunk_metadata,
                        embedding=mc.embedding,
                    )
                    db.add(nc)

            await db.commit()
    except Exception as exc:
        logger.warning("Demo document cloning skipped or failed: %s", exc)

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = await create_access_token(data={"sub": session_user.email}, expires_delta=access_token_expires)
    logger.info("Demo JWT successfully issued for %s", session_email)
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )

