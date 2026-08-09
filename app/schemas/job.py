from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

JobState = Literal["queued", "processing", "completed", "failed"]

class JobRead(BaseModel):
    id: int
    document_id: int | None
    user_id: int
    status: JobState
    progress: int = Field(..., ge=0, le=100)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobAccepted(BaseModel):
    job_id: int = Field(..., ge=1)
    document_id: int = Field(..., ge=1)
    status: Literal["queued"]
    status_url: str
