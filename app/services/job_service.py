from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job


async def get_job_for_user(db: AsyncSession, job_id: int, user_id: int) -> Job | None:
    result = await db.execute(select(Job).where(Job.id == job_id, Job.user_id == user_id))
    return result.scalar_one_or_none()


async def update_job(
    db: AsyncSession,
    job: Job,
    *,
    status: str,
    progress: int,
    error_message: str | None = None,
) -> Job:
    job.status = status
    job.progress = progress
    job.error_message = error_message
    await db.commit()
    await db.refresh(job)
    return job
