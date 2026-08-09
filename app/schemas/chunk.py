from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional

class ChunkRead(BaseModel):
    id: int
    document_id: int
    page_id: Optional[int]
    chunk_type: str
    content: str
    metadata: Optional[dict]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
