from typing import TYPE_CHECKING

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.page import Page

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

# Quoted annotation: CrossEncoder only exists for type checkers, never at runtime.
_reranker: "CrossEncoder | None" = None


def warm_up_reranker() -> bool:
    """Preload reranker weights in a worker thread without blocking the event loop."""
    global _reranker
    if not getattr(settings, "reranking_enabled", True):
        return False
    if _reranker is None:
        from sentence_transformers import CrossEncoder

        _reranker = CrossEncoder(settings.reranker_model)
        return True
    return False


def rerank(question: str, candidates: list[tuple[Chunk, Page]], limit: int) -> list[tuple[Chunk, Page]]:
    global _reranker
    if _reranker is None:
        warm_up_reranker()
    if _reranker is None:
        return candidates[:limit]
    scores = _reranker.predict([(question, chunk.content) for chunk, _ in candidates])
    return [candidate for _, candidate in sorted(zip(scores, candidates), key=lambda item: float(item[0]), reverse=True)[:limit]]
