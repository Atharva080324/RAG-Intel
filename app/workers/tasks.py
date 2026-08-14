"""Reliable Celery tasks for document ingestion."""

import asyncio
import tempfile
import time
from datetime import datetime
from pathlib import Path

from celery.utils.log import get_task_logger
from sqlalchemy import delete
from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.database import async_session
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.job import Job
from app.models.page import Page
from app.services.ingestion_service import chunk_text, embed, extract_pdf, extract_text
from app.services.storage import get_storage
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)

MAX_RETRIES = 3


def _is_retryable_error(exc: Exception) -> bool:
    """Return whether an ingestion error is likely to succeed on a later attempt."""
    if isinstance(exc, (ConnectionError, TimeoutError, OSError, OperationalError, DBAPIError)):
        return True

    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return status_code == 429 or (isinstance(status_code, int) and status_code >= 500)


async def _record_failure(job_id: int, attempt: int, *, retrying: bool) -> None:
    """Persist a safe job state without exposing provider errors to API clients."""
    async with async_session() as db:
        job = await db.get(Job, job_id)
        if not job:
            return
        document = await db.get(Document, job.document_id)

        job.attempt_count = max(job.attempt_count, attempt)
        job.progress = 0
        if retrying:
            job.status = "queued"
            job.error_message = f"Transient ingestion failure; retry {attempt} of {MAX_RETRIES}."
            if document:
                document.status = "pending"
        else:
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            job.error_message = f"Ingestion failed after {attempt} attempt(s)."
            if document:
                document.status = "failed"
        await db.commit()


async def _process_document(job_id: int, attempt: int) -> dict[str, int | str] | None:
    started = time.perf_counter()
    async with async_session() as db:
        job = await db.get(Job, job_id)
        if not job:
            logger.error("ingestion_job_missing job_id=%s", job_id)
            return None

        document = await db.get(Document, job.document_id)
        if not document:
            job.status, job.progress = "failed", 0
            job.attempt_count = max(job.attempt_count, attempt)
            job.completed_at = datetime.utcnow()
            job.error_message = "Source document not found."
            await db.commit()
            logger.error("ingestion_document_missing job_id=%s document_id=%s", job_id, job.document_id)
            return None

        # A late redelivery after success must not re-ingest the same document.
        if job.status == "completed" and document.status == "completed":
            logger.info("ingestion_already_completed job_id=%s document_id=%s", job.id, document.id)
            return {"job_id": job.id, "document_id": document.id, "status": "completed"}

        job.status, job.progress, job.error_message = "processing", 10, None
        job.attempt_count = max(job.attempt_count, attempt)
        job.started_at = job.started_at or datetime.utcnow()
        job.completed_at = None
        document.status = "processing"

        # Derived pages/chunks can be recreated from the source file. Clearing them
        # first makes retries idempotent after a partial database write.
        await db.execute(delete(Chunk).where(Chunk.document_id == document.id))
        await db.execute(delete(Page).where(Page.document_id == document.id))
        await db.commit()
        logger.info("ingestion_started job_id=%s document_id=%s attempt=%s", job.id, document.id, attempt)

        # The worker runs as a separate Render service with its own ephemeral
        # filesystem, so the uploaded file must be pulled back from shared object
        # storage (R2 in production, local fallback in development) into a
        # per-task temporary file before extraction.
        source_key = document.source_path
        file_ext = Path(source_key).suffix.lower()
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_path = Path(tmp_dir) / f"source{file_ext}"
            local_path.write_bytes(await get_storage().download(source_key))
            pages = extract_pdf(str(local_path)) if file_ext == ".pdf" else extract_text(str(local_path))
        if not any(page.text or page.tables for page in pages):
            raise ValueError("No extractable content found")

        job.progress = 35
        await db.commit()

        pending_chunks: list[tuple[Chunk, str]] = []
        for extracted in pages:
            page = Page(document_id=document.id, page_number=extracted.page_number, page_text=extracted.text)
            db.add(page)
            await db.flush()
            for text_content in chunk_text(extracted.text):
                chunk = Chunk(
                    document_id=document.id,
                    page_id=page.id,
                    chunk_type="text",
                    content=text_content,
                    chunk_metadata={"page_number": extracted.page_number},
                )
                db.add(chunk)
                pending_chunks.append((chunk, text_content))
            for table in extracted.tables:
                chunk = Chunk(
                    document_id=document.id,
                    page_id=page.id,
                    chunk_type="table",
                    content=table,
                    chunk_metadata={"page_number": extracted.page_number, "format": "markdown"},
                )
                db.add(chunk)
                pending_chunks.append((chunk, table))
        await db.flush()
        job.progress = 60
        await db.commit()
        logger.info(
            "ingestion_extracted job_id=%s document_id=%s pages=%s chunks=%s",
            job.id,
            document.id,
            len(pages),
            len(pending_chunks),
        )

        for offset in range(0, len(pending_chunks), 32):
            batch = pending_chunks[offset : offset + 32]
            vectors = embed([item[1] for item in batch])
            for chunk, vector in zip((item[0] for item in batch), vectors, strict=True):
                chunk.embedding = vector
            job.progress = 60 + int(35 * min(offset + len(batch), len(pending_chunks)) / max(1, len(pending_chunks)))
            await db.commit()

        job.status, job.progress, job.error_message = "completed", 100, None
        job.completed_at = datetime.utcnow()
        document.status = "completed"
        await db.commit()
        logger.info(
            "ingestion_completed job_id=%s document_id=%s pages=%s chunks=%s duration_seconds=%.2f",
            job.id,
            document.id,
            len(pages),
            len(pending_chunks),
            time.perf_counter() - started,
        )
        return {"job_id": job.id, "document_id": document.id, "status": job.status}


@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_document",
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=MAX_RETRIES,
)
def process_document(self, job_id: int):
    """Ingest one document with bounded retries for transient failures."""
    attempt = self.request.retries + 1
    try:
        return asyncio.run(_process_document(job_id, attempt))
    except Exception as exc:
        retrying = _is_retryable_error(exc) and self.request.retries < MAX_RETRIES
        asyncio.run(_record_failure(job_id, attempt, retrying=retrying))
        if retrying:
            countdown = min(60, 2**self.request.retries)
            logger.warning(
                "ingestion_retry_scheduled job_id=%s attempt=%s countdown_seconds=%s error_type=%s",
                job_id,
                attempt,
                countdown,
                type(exc).__name__,
            )
            raise self.retry(exc=exc, countdown=countdown)
        logger.exception(
            "ingestion_failed job_id=%s attempt=%s error_type=%s",
            job_id,
            attempt,
            type(exc).__name__,
        )
        raise
