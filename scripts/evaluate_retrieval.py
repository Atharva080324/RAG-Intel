"""Run retrieval-only evaluation cases without generating LLM answers.

Usage:
    uv run python scripts/evaluate_retrieval.py --cases evaluation/cases.example.json
"""

import argparse
import asyncio
import json
from pathlib import Path
from statistics import mean

from app.core.database import async_session
from app.services.retrieval_service import retrieve_document_chunks_with_diagnostics


def page_metrics(expected_pages: list[int], retrieved_pages: list[int]) -> dict[str, float | bool | None]:
    expected = set(expected_pages)
    first_rank = next((index for index, page in enumerate(retrieved_pages, start=1) if page in expected), None)
    return {
        "hit_at_k": first_rank is not None,
        "reciprocal_rank": round(1 / first_rank, 4) if first_rank else 0.0,
        "first_relevant_rank": first_rank,
    }


async def evaluate(cases: list[dict[str, object]]) -> list[dict[str, object]]:
    results = []
    async with async_session() as db:
        for case in cases:
            retrieval = await retrieve_document_chunks_with_diagnostics(
                db,
                document_id=int(case["document_id"]),
                user_id=int(case["user_id"]),
                question=str(case["question"]),
                limit=int(case.get("limit", 8)),
            )
            pages = [page.page_number for _, page in retrieval.chunks if page]
            results.append(
                {
                    "id": case["id"],
                    "question": case["question"],
                    "expected_pages": case["expected_pages"],
                    "retrieved_pages": pages,
                    "metrics": page_metrics(list(case["expected_pages"]), pages),
                    "diagnostics": retrieval.diagnostics(),
                }
            )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval hit rate and latency.")
    parser.add_argument("--cases", type=Path, required=True, help="Path to an evaluation cases JSON file")
    parser.add_argument("--output", type=Path, default=Path("evaluation/results.json"))
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    results = asyncio.run(evaluate(cases))
    summary = {
        "case_count": len(results),
        "hit_at_k": round(mean(item["metrics"]["hit_at_k"] for item in results), 4) if results else 0.0,
        "mean_reciprocal_rank": round(mean(item["metrics"]["reciprocal_rank"] for item in results), 4) if results else 0.0,
        "average_retrieval_latency_ms": round(mean(item["diagnostics"]["retrieval_latency_ms"] for item in results)) if results else 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
