import asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.page import Page
from app.services.ingestion_service import embed
from app.services.reranker_service import rerank


def _base_query(document_id: int, user_id: int):
    return (select(Chunk, Page).join(Document, Chunk.document_id == Document.id).outerjoin(Page, Chunk.page_id == Page.id)
            .where(Document.id == document_id, Document.user_id == user_id, Document.status == "completed"))


async def retrieve_document_chunks(db: AsyncSession, *, document_id: int, user_id: int, question: str, limit: int) -> list[tuple[Chunk, Page]]:
    """Fuse semantic and exact-term rankings, then rerank the bounded set."""
    candidate_limit = settings.reranker_candidate_limit
    vector = (await asyncio.to_thread(embed, [question], is_query=True))[0]
    semantic = await db.execute(_base_query(document_id, user_id).order_by(Chunk.embedding.cosine_distance(vector)).limit(candidate_limit))
    tsquery = func.websearch_to_tsquery("english", question)
    lexical = await db.execute(_base_query(document_id, user_id).where(Chunk.search_vector.op("@@")(tsquery))
                               .order_by(func.ts_rank_cd(Chunk.search_vector, tsquery).desc()).limit(candidate_limit))
    fused: dict[int, tuple[float, tuple[Chunk, Page]]] = {}
    for result_set in (list(semantic.all()), list(lexical.all())):
        for rank, candidate in enumerate(result_set, start=1):
            score, _ = fused.get(candidate[0].id, (0.0, candidate))
            fused[candidate[0].id] = (score + 1.0 / (60 + rank), candidate)
    candidates = [item[1] for item in sorted(fused.values(), key=lambda item: item[0], reverse=True)[:candidate_limit]]
    if not candidates:
        return []
    return await asyncio.to_thread(rerank, question, candidates, limit)


def build_rag_prompt(question: str, chunks: list[tuple[Chunk, Page]]) -> str:
    sources = []
    for index, (chunk, page) in enumerate(chunks, start=1):
        sources.append(f"[S{index} | page {page.page_number if page else 0} | {chunk.chunk_type}]\n{chunk.content}")
    return f"""Answer only from the supplied document excerpts. If the excerpts do not support an answer, say so clearly.
Every factual claim must cite one or more source markers exactly as [S1] or [S2]. Do not invent citations.

Question: {question}

Document excerpts:
{"\n\n".join(sources)}
"""
