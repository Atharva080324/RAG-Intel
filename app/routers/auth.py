from datetime import timedelta
from secrets import token_urlsafe
from urllib.parse import urlencode, quote
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.core.dependencies import get_db
from app.core.security import verify_password, create_access_token
from app.services.user_service import (
    create_google_user,
    create_user,
    get_user_by_email,
    get_user_by_google_subject,
)
from app.services.cache_service import delete_cache, get_cache, set_cache
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
            f"http://127.0.0.1:8501/?oauth_error={quote(error)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    _google_configured()
    if not code or not state:
        return RedirectResponse(
            "http://127.0.0.1:8501/?oauth_error=invalid_request",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    state_key = f"oauth:google:state:{state}"
    cached_state = await get_cache(state_key)
    if not cached_state:
        return RedirectResponse(
            "http://127.0.0.1:8501/?oauth_error=invalid_state",
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
            "http://127.0.0.1:8501/?oauth_error=oauth_exchange_failed",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    google_subject = profile.get("sub")
    email = profile.get("email", "").strip().lower()
    if not google_subject or not email or profile.get("email_verified") is not True:
        return RedirectResponse(
            "http://127.0.0.1:8501/?oauth_error=email_not_verified",
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
            "http://127.0.0.1:8501/?oauth_error=inactive_user",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    access_token = await create_access_token(data={"sub": user.email})
    redirect_target = f"http://127.0.0.1:8501/?token={quote(access_token)}"
    return RedirectResponse(redirect_target, status_code=status.HTTP_303_SEE_OTHER)
