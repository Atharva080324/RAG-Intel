# Retrieval evaluation

The evaluation runner measures retrieval quality without calling the generation model. Each case includes a document owner, document ID, question, and the page(s) expected to appear in the reranked results.

Run it against your local development data:

```powershell
uv run python scripts/evaluate_retrieval.py --cases evaluation/cases.example.json
```

The script prints and writes three portfolio-friendly metrics:

- `hit_at_k`: whether any expected page appeared in the final reranked chunks.
- `mean_reciprocal_rank`: how early the first expected page appeared.
- `average_retrieval_latency_ms`: embedding, hybrid search, and reranking duration.

Copy `cases.example.json` to a private `cases.json` and expand it to at least 15 focused questions before deployment. Update the document/user IDs to match the database used for the run. Do not commit generated `results.json` files or customer-document evaluation data.
