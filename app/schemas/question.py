from typing import Any
from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    document_id: int = Field(..., ge=1)
    question: str = Field(..., min_length=3, max_length=4000)


class Citation(BaseModel):
    page_number: int = Field(..., ge=1)
    chunk_type: str


class AnalyticsResponse(BaseModel):
    """Table analytics result (legacy response model – kept for backwards compat)."""
    operation: str
    column: str
    value: int | float
    rows_used: int = Field(..., ge=0)
    source_chunk_id: int = Field(..., ge=1)


class RetrievalTrace(BaseModel):
    """Observability data for a single retrieval pass.

    All fields are counts or latencies; no document content is included so
    the trace is safe to log and display to recruiters.
    """
    query_type: str = Field(..., description="'table' or 'text'")
    semantic_candidates: int = Field(..., ge=0)
    lexical_candidates: int = Field(..., ge=0)
    fused_candidates: int = Field(..., ge=0)
    returned_chunks: int = Field(..., ge=0)
    retrieval_latency_ms: int = Field(..., ge=0)
    rewritten_queries: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    """Full /questions/analyze response including the retrieval trace.

    Additive superset of AnalyticsResponse: existing callers that only
    read ``operation``/``column``/``value``/``rows_used``/``source_chunk_id``
    continue to work.
    """
    operation: str
    column: str
    value: int | float
    rows_used: int = Field(..., ge=0)
    source_chunk_id: int = Field(..., ge=1)
    retrieval_trace: RetrievalTrace | None = None
