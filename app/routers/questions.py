import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.question import AnalyticsResponse, QuestionRequest
from app.services.generation_service import stream_groq_answer
from app.services.agent_service import corrective_rag_graph
from app.services.analytics_service import analyze_table_question
from app.services.retrieval_service import retrieve_document_chunks

router = APIRouter()


def _sse(event: str, data: object) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode("utf-8")


@router.post("/analyze", response_model=AnalyticsResponse)
async def analyze_question(
    request: QuestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsResponse:
    candidates = await retrieve_document_chunks(
        db,
        document_id=request.document_id,
        user_id=current_user.id,
        question=request.question,
        limit=settings.retrieval_top_k,
    )
    table_chunks = [chunk for chunk, _ in candidates if chunk.chunk_type == "table"]
    try:
        return analyze_table_question(request.question, table_chunks)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/stream")
async def stream_answer(
    request: QuestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    if not settings.groq_api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Answer generation is not configured")
    result = await corrective_rag_graph.ainvoke(
        {"question": request.question, "document_id": request.document_id, "user_id": current_user.id},
        {"configurable": {"db": db}, "recursion_limit": 12},
    )
    if not result.get("chunks"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Completed document with indexed content not found")
    prompt = result["prompt"]
    citations = result["citations"]
    workflow = {"intent": result["intent"], "rewrite_attempts": result["attempts"], "relevance_score": round(result["relevance_score"], 3)}

    async def event_stream() -> AsyncIterator[bytes]:
        try:
            yield _sse("workflow", workflow)
            async for token in stream_groq_answer(prompt):
                yield _sse("token", {"text": token})
            yield _sse("citations", citations)
            yield _sse("done", {})
        except Exception:
            yield _sse("error", {"detail": "Answer generation failed"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
