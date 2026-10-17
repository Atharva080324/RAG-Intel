import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.question import AnalyticsResponse, AnalyzeResponse, QuestionRequest
from app.services.generation_service import stream_groq_answer
from app.services.agent_service import corrective_rag_graph
from app.services.analytics_service import analyze_table_question
from app.services.rate_limit_service import TooManyRequestsError, check_daily_cap
from app.services.retrieval_service import retrieve_document_chunks_with_diagnostics

router = APIRouter()


def _sse(event: str, data: object) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode("utf-8")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_question(
    request: QuestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyzeResponse:
    """Retrieve evidence, run table analytics, and return the retrieval trace.

    The ``retrieval_trace`` field is additive — existing callers that only use
    ``operation``/``column``/``value``/``rows_used``/``source_chunk_id`` are
    unaffected.
    """
    try:
        await check_daily_cap(current_user.id, "question", settings.daily_question_limit)
    except TooManyRequestsError as exc:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": str(exc)},
            headers={"Retry-After": str(exc.retry_after)},
        )

    result = await retrieve_document_chunks_with_diagnostics(
        db,
        document_id=request.document_id,
        user_id=current_user.id,
        question=request.question,
        limit=settings.retrieval_top_k,
    )
    table_chunks = [chunk for chunk, _ in result.chunks if chunk.chunk_type == "table"]
    try:
        analytics = analyze_table_question(request.question, table_chunks)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return {
        **analytics,
        "retrieval_trace": {
            "query_type": "table" if table_chunks else "text",
            **result.diagnostics(),
        },
    }


@router.post("/stream")
async def stream_answer(
    request: QuestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    try:
        await check_daily_cap(current_user.id, "question", settings.daily_question_limit)
    except TooManyRequestsError as exc:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": str(exc)},
            headers={"Retry-After": str(exc.retry_after)},
        )

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
    insufficient_evidence = result["relevance_score"] < settings.min_grounding_score

    # ── Retrieval trace (Phase 1 requirement) ─────────────────────────────────
    # Expose the full corrective-RAG trace so the React UI can render the
    # Retrieval Inspector panel.  Field names are additive and non-breaking.
    diag = result.get("retrieval_diagnostics", {})
    workflow = {
        "intent": result["intent"],
        "rewrite_attempts": result["attempts"],
        "relevance_score": round(result["relevance_score"], 3),
        "minimum_grounding_score": settings.min_grounding_score,
        "answer_mode": "insufficient_evidence" if insufficient_evidence else "grounded_answer",
        "retrieval": {
            **diag,
            # Rewritten queries produced by the corrective loop.
            "rewritten_queries": _collect_rewrites(result),
        },
    }

    async def event_stream() -> AsyncIterator[bytes]:
        try:
            yield _sse("workflow", workflow)
            if insufficient_evidence:
                yield _sse(
                    "token",
                    {
                        "text": "I could not find enough relevant evidence in this document to answer that reliably. "
                        "Try naming a topic, section, person, or page from the uploaded document."
                    },
                )
                yield _sse("citations", citations)
                yield _sse("done", {})
                return
            async for token in stream_groq_answer(prompt):
                yield _sse("token", {"text": token})
            yield _sse("citations", citations)
            yield _sse("done", {})
        except Exception as exc:
            logger.exception("Answer generation failed in stream: %s", exc)
            yield _sse("error", {"detail": f"Answer generation failed: {exc}"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        # X-Accel-Buffering: no disables Nginx/Caddy proxy buffering so each
        # SSE token is flushed to the browser immediately.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _collect_rewrites(result: dict) -> list[str]:
    """Return the list of rewritten queries produced by the corrective loop.

    The LangGraph state carries ``retrieval_query`` from the last retrieve node;
    if attempts > 0 the original question was rewritten at least once.
    """
    rewrites: list[str] = []
    query = result.get("retrieval_query", "")
    question = result.get("question", "")
    if query and query != question:
        rewrites.append(query)
    return rewrites
