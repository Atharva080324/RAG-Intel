from sentence_transformers import CrossEncoder
from app.core.config import settings
from app.models.chunk import Chunk
from app.models.page import Page

_reranker: CrossEncoder | None = None

def rerank(question: str, candidates: list[tuple[Chunk, Page]], limit: int) -> list[tuple[Chunk, Page]]:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(settings.reranker_model)
    scores = _reranker.predict([(question, chunk.content) for chunk, _ in candidates])
    return [candidate for _, candidate in sorted(zip(scores, candidates), key=lambda item: float(item[0]), reverse=True)[:limit]]
