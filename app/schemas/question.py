from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    document_id: int = Field(..., ge=1)
    question: str = Field(..., min_length=3, max_length=4000)


class Citation(BaseModel):
    page_number: int = Field(..., ge=1)
    chunk_type: str


class AnalyticsResponse(BaseModel):
    operation: str
    column: str
    value: int | float
    rows_used: int = Field(..., ge=0)
    source_chunk_id: int = Field(..., ge=1)

