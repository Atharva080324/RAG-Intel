from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class DocumentCreate(BaseModel):
    filename: str
    content_hash: str
    source_path: str

class DocumentRead(BaseModel):
    id: int
    filename: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentStatusRead(BaseModel):
    document_id: int = Field(..., ge=1)
    status: Literal["pending", "queued", "processing", "completed", "failed"]
    updated_at: datetime


class DocumentListRead(BaseModel):
    items: list[DocumentRead]
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
