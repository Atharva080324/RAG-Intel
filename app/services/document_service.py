from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.job import Job
from app.models.document import Document

async def get_document_by_hash(db: AsyncSession, user_id: int, content_hash: str) -> Document | None:
    result = await db.execute(
        select(Document).where(Document.user_id == user_id, Document.content_hash == content_hash)
    )
    return result.scalar_one_or_none()

async def create_document(db: AsyncSession, user_id: int, filename: str, content_hash: str, source_path: str) -> Document:
    document = Document(
        user_id=user_id,
        filename=filename,
        content_hash=content_hash,
        status="pending",
        source_path=source_path,
    )
    db.add(document)
    await db.flush()
    return document


async def create_ingestion_job(db: AsyncSession, document_id: int, user_id: int, task_id: str) -> Job:
    job = Job(document_id=document_id, user_id=user_id, task_id=task_id, status="queued", progress=0)
    db.add(job)
    await db.flush()
    return job

async def get_documents_for_user(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 10) -> List[Document]:
    result = await db.execute(select(Document).where(Document.user_id == user_id).offset(skip).limit(limit))
    return result.scalars().all()

async def get_document_by_id(db: AsyncSession, document_id: int) -> Document | None:
    return await db.get(Document, document_id)

async def update_document_status(db: AsyncSession, document: Document, status: str) -> Document:
    document.status = status
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document
