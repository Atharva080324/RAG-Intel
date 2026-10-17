from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.dependencies import get_db
from app.core.security import get_current_user
from app.services.document_service import (
    create_document,
    create_ingestion_job,
    get_document_by_hash,
    get_document_by_id,
    get_documents_for_user,
)
from app.services.rate_limit_service import TooManyRequestsError, check_daily_cap
from app.services.storage import ObjectStorageError, document_key, get_storage
from app.workers.tasks import process_document
from app.models.user import User
from app.schemas.document import DocumentListRead, DocumentRead, DocumentStatusRead
from app.schemas.job import JobAccepted
import hashlib
from uuid import uuid4

router = APIRouter()

ALLOWED_MIME_TYPES = {"application/pdf", "text/plain", "text/markdown"}


def _safe_filename(filename: str | None) -> str:
    name = Path(filename or "").name
    if not name or name in {".", ".."} or len(name) > 255:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid filename")
    allowed_extensions = {f".{extension.strip().lower()}" for extension in settings.allowed_upload_extensions.split(",")}
    if Path(name).suffix.lower() not in allowed_extensions:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type")
    return name

@router.post("/upload", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await check_daily_cap(current_user.id, "upload", settings.daily_upload_limit)
    except TooManyRequestsError as exc:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": str(exc)},
            headers={"Retry-After": str(exc.retry_after)},
        )
    filename = _safe_filename(file.filename)
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported media type")
    content = await file.read(settings.max_upload_size_bytes + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="File must not be empty")
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is too large")
    if Path(filename).suffix.lower() == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid PDF content")
    content_hash = hashlib.sha256(content).hexdigest()
    existing_doc = await get_document_by_hash(db, current_user.id, content_hash)
    if existing_doc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document already uploaded")

    # Upload to shared object storage (R2 in production, local fallback in dev)
    # rather than a service-local directory that the separate worker cannot see.
    key = document_key(current_user.id, filename, uuid4().hex)
    try:
        await get_storage().upload(key, content)
    except ObjectStorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to store uploaded document") from exc

    task_id = uuid4().hex
    try:
        document = await create_document(db, current_user.id, filename, content_hash, key)
        document.status = "queued"
        job = await create_ingestion_job(db, document.id, current_user.id, task_id)
        await db.commit()
        await db.refresh(job)
    except IntegrityError:
        await db.rollback()
        await get_storage().delete(key)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document already uploaded")
    except Exception:
        await db.rollback()
        await get_storage().delete(key)
        raise

    try:
        process_document.apply_async(args=[job.id], task_id=task_id)
    except Exception:
        # Preserve the record for polling and make broker failures explicit.
        job.status = "failed"
        job.progress = 0
        job.error_message = "Unable to queue ingestion job"
        await db.commit()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to queue ingestion job")

    return {"job_id": job.id, "document_id": document.id, "status": "queued", "status_url": f"/jobs/{job.id}"}

@router.get("/", response_model=DocumentListRead)
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
):
    documents = await get_documents_for_user(db, current_user.id, skip=skip, limit=limit)
    return {"items": documents, "skip": skip, "limit": limit}

@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(document_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    document = await get_document_by_id(db, document_id)
    if not document or document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document

@router.get("/{document_id}/status", response_model=DocumentStatusRead)
async def document_status(document_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    document = await get_document_by_id(db, document_id)
    if not document or document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return {"document_id": document.id, "status": document.status, "updated_at": document.updated_at}
