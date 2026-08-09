from celery.utils.log import get_task_logger
from app.workers.celery_app import celery_app
from app.core.database import async_session
from app.models.document import Document
from app.models.job import Job
from app.models.page import Page
from app.models.chunk import Chunk
from app.services.ingestion_service import chunk_text, embed, extract_pdf, extract_text
import asyncio

logger = get_task_logger(__name__)

@celery_app.task(name="app.workers.tasks.process_document")
def process_document(job_id: int):
    async def _process():
        async with async_session() as db:
            job = await db.get(Job, job_id)
            if not job:
                logger.error("Job not found %s", job_id)
                return
            document = await db.get(Document, job.document_id)
            if not document:
                job.status, job.progress, job.error_message = "failed", 0, "Source document not found"
                await db.commit()
                return
            try:
                job.status, job.progress, job.error_message = "processing", 10, None
                document.status = "processing"
                await db.commit()
                source_path = document.source_path
                pages = extract_pdf(source_path) if source_path.lower().endswith(".pdf") else extract_text(source_path)
                if not any(page.text or page.tables for page in pages):
                    raise ValueError("No extractable content found")
                job.progress = 35
                await db.commit()

                pending_chunks: list[tuple[Chunk, str]] = []
                for extracted in pages:
                    page = Page(document_id=document.id, page_number=extracted.page_number, page_text=extracted.text)
                    db.add(page)
                    await db.flush()
                    for text in chunk_text(extracted.text):
                        chunk = Chunk(document_id=document.id, page_id=page.id, chunk_type="text", content=text, chunk_metadata={"page_number": extracted.page_number})
                        db.add(chunk)
                        pending_chunks.append((chunk, text))
                    for table in extracted.tables:
                        chunk = Chunk(document_id=document.id, page_id=page.id, chunk_type="table", content=table, chunk_metadata={"page_number": extracted.page_number, "format": "markdown"})
                        db.add(chunk)
                        pending_chunks.append((chunk, table))
                await db.flush()
                job.progress = 60
                await db.commit()

                for offset in range(0, len(pending_chunks), 32):
                    batch = pending_chunks[offset:offset + 32]
                    for chunk, vector in zip((item[0] for item in batch), embed([item[1] for item in batch])):
                        chunk.embedding = vector
                    job.progress = 60 + int(35 * min(offset + len(batch), len(pending_chunks)) / max(1, len(pending_chunks)))
                    await db.commit()
                job.status, job.progress = "completed", 100
                document.status = "completed"
                await db.commit()
                return {"job_id": job.id, "document_id": document.id, "status": job.status}
            except Exception as exc:
                logger.exception("Job %s failed", job_id)
                job.status, job.progress = "failed", 0
                job.error_message = "Ingestion failed"
                document.status = "failed"
                await db.commit()
                raise exc

    return asyncio.run(_process())
