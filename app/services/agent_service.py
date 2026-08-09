"""Bounded corrective-RAG workflow implemented with LangGraph."""
import re
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.page import Page
from app.services.retrieval_service import build_rag_prompt, retrieve_document_chunks

_TABLE_TERMS = {"table", "row", "column", "cell", "total", "amount", "price", "revenue", "balance", "percentage"}


class AgentState(TypedDict, total=False):
    question: str
    retrieval_query: str
    document_id: int
    user_id: int
    intent: Literal["table", "text"]
    attempts: int
    chunks: list[tuple[Chunk, Page]]
    relevance_score: float
    prompt: str
    citations: list[dict[str, object]] 


def _terms(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]{3,}", text.lower()) if word not in {"the", "and", "with", "from", "that", "this", "what", "does"}}


async def route_query(state: AgentState) -> dict:
    terms = _terms(state["question"])
    return {"intent": "table" if terms & _TABLE_TERMS else "text", "retrieval_query": state["question"], "attempts": 0}


async def retrieve(state: AgentState, config: dict) -> dict:
    db: AsyncSession = config["configurable"]["db"]
    chunks = await retrieve_document_chunks(
        db,
        document_id=state["document_id"],
        user_id=state["user_id"],
        question=state["retrieval_query"],
        limit=settings.retrieval_top_k,
    )
    return {"chunks": chunks}


async def grade_relevance(state: AgentState) -> dict:
    query_terms = _terms(state["retrieval_query"])
    if not state.get("chunks") or not query_terms:
        return {"relevance_score": 0.0}
    # Transparent lexical grounding check complements semantic retrieval and avoids an extra model call.
    best = max(len(query_terms & _terms(chunk.content)) / len(query_terms) for chunk, _ in state["chunks"])
    return {"relevance_score": best}


def after_grade(state: AgentState) -> Literal["rewrite", "prepare"]:
    return "rewrite" if state["relevance_score"] < 0.15 and state["attempts"] < 2 else "prepare"


async def rewrite_query(state: AgentState) -> dict:
    suffix = " Focus on tabular values, row labels, columns, and exact numbers." if state["intent"] == "table" else " Include relevant definitions, entities, and supporting details."
    return {"retrieval_query": state["question"] + suffix, "attempts": state["attempts"] + 1}


async def prepare_answer(state: AgentState) -> dict:
    chunks = state.get("chunks", [])
    citations = [
        {"source": f"S{index}", "page_number": page.page_number, "chunk_type": chunk.chunk_type}
        for index, (chunk, page) in enumerate(chunks, start=1)
        if page
    ]
    return {"prompt": build_rag_prompt(state["question"], chunks), "citations": citations}


def build_corrective_rag_graph():
    graph = StateGraph(AgentState)
    graph.add_node("route", route_query)
    graph.add_node("retrieve", retrieve)
    graph.add_node("grade", grade_relevance)
    graph.add_node("rewrite", rewrite_query)
    graph.add_node("prepare", prepare_answer)
    graph.add_edge(START, "route")
    graph.add_edge("route", "retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges("grade", after_grade, {"rewrite": "rewrite", "prepare": "prepare"})
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("prepare", END)
    return graph.compile()


corrective_rag_graph = build_corrective_rag_graph()
