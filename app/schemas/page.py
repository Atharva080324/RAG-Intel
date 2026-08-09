from datetime import datetime
from pydantic import BaseModel, ConfigDict

class PageRead(BaseModel):
    id: int
    document_id: int
    page_number: int
    page_text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
