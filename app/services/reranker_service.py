from typing import TYPE_CHECKING

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.page import Page

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

# Quoted annotation: CrossEncoder only exists for type checkers, never at runtime.
_reranker: "CrossEncoder | None" = None


def rerank(question: str, candidates: list[tuple[Chunk, Page]], limit: int) -> list[tuple[Chunk, Page]]:
    global _reranker
    if _reranker is None:
        # Lazy-load on first use so importing this module (e.g. at API boot) never
        # imports sentence_transformers/torch — that alone costs ~400 MB RSS and
        # OOM-kills 1 GB containers. Weights load only when reranking actually runs.
        from sentence_transformers import CrossEncoder

        _reranker = CrossEncoder(settings.reranker_model)
    scores = _reranker.predict([(question, chunk.content) for chunk, _ in candidates])
    return [candidate for _, candidate in sorted(zip(scores, candidates), key=lambda item: float(item[0]), reverse=True)[:limit]]
