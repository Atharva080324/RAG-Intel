#!/usr/bin/env python
"""Cleanup script for demo mode uploads.

Runs via cron (e.g., daily at 3:00 AM) to purge documents uploaded by the demo
user older than 24 hours, preventing storage accumulation on the Oracle Always Free VM.

Crontab entry (run on the Oracle VM host):
    0 3 * * * cd /home/ubuntu/rag-document-intelligence && docker compose -f docker-compose.prod.yml exec -T api python scripts/cleanup_demo_uploads.py >> /var/log/rag-cleanup.log 2>&1
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete
from app.core.config import settings
from app.core.database import async_session
from app.models.user import User
from app.models.document import Document
from app.models.job import Job
from app.models.page import Page
from app.models.chunk import Chunk
from app.services.storage import get_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cleanup_demo")


async def cleanup_demo_uploads(retention_hours: int = 24) -> int:
    """Purge ephemeral demo users and their uploads older than retention_hours.

    Guarantees master seed data (demo@rag-demo.internal) is never deleted.
    """
    master_seed_email = settings.demo_user_email.strip().lower()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
    cutoff_dt = cutoff.replace(tzinfo=None)
    storage = get_storage()
    deleted_docs_count = 0
    deleted_users_count = 0

    async with async_session() as db:
        # 1. Clean up ephemeral per-session demo users (demo_<id>@rag-demo.internal)
        ephemeral_users = (
            await db.execute(
                select(User).where(
                    User.email.like("demo_%@rag-demo.internal"),
                    User.created_at < cutoff_dt,
                )
            )
        ).scalars().all()

        for user in ephemeral_users:
            logger.info("Purging expired demo session user %s (id=%d)...", user.email, user.id)
            # Find and clean their documents
            user_docs = (
                await db.execute(select(Document).where(Document.user_id == user.id))
            ).scalars().all()

            for doc in user_docs:
                await db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
                await db.execute(delete(Page).where(Page.document_id == doc.id))
                await db.execute(delete(Job).where(Job.document_id == doc.id))
                # Only delete storage blob if it is not a shared seed path
                if not any(seed_name in doc.filename for seed_name in ["rag_architecture_guide", "quarterly_financial_report"]):
                    try:
                        await storage.delete(doc.source_path)
                    except Exception as e:
                        logger.warning("Could not delete blob %s: %s", doc.source_path, e)
                await db.delete(doc)
                deleted_docs_count += 1

            await db.delete(user)
            deleted_users_count += 1

        # 2. For master demo user: keep seed documents intact, only purge non-seed uploads older than retention_hours
        master_user = (
            await db.execute(select(User).where(User.email == master_seed_email))
        ).scalar_one_or_none()

        if master_user:
            non_seed_docs = (
                await db.execute(
                    select(Document).where(
                        Document.user_id == master_user.id,
                        Document.created_at < cutoff_dt,
                        ~Document.filename.in_(["rag_architecture_guide.pdf", "quarterly_financial_report.pdf"]),
                    )
                )
            ).scalars().all()

            for doc in non_seed_docs:
                logger.info("Cleaning expired non-seed document %d (%s) from master user...", doc.id, doc.filename)
                await db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
                await db.execute(delete(Page).where(Page.document_id == doc.id))
                await db.execute(delete(Job).where(Job.document_id == doc.id))
                try:
                    await storage.delete(doc.source_path)
                except Exception as e:
                    logger.warning("Could not delete blob %s: %s", doc.source_path, e)
                await db.delete(doc)
                deleted_docs_count += 1

        await db.commit()

    logger.info(
        "Successfully purged %d expired demo user(s) and %d document(s). Seed source data preserved.",
        deleted_users_count,
        deleted_docs_count,
    )
    return deleted_docs_count


if __name__ == "__main__":
    count = asyncio.run(cleanup_demo_uploads())
    print(f"Purged {count} expired demo documents.")

