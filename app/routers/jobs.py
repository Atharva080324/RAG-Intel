from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.job import JobRead
from app.services.job_service import get_job_for_user

router = APIRouter()


@router.get("/{job_id}", response_model=JobRead)
async def get_job_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll an ingestion job. Jobs are always scoped to the authenticated owner."""
    job = await get_job_for_user(db, job_id, current_user.id)
    if job is None:
        # Do not disclose whether another user's job exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
