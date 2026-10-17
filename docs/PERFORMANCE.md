# Performance Benchmark & Comparison

This document records baseline latency measurements for the RAG Document Intelligence platform comparing **Local Development** (Windows 10, Neon PostgreSQL, Upstash Redis) against the **Production Oracle Cloud ARM VM** (VM.Standard.A1.Flex, co-located Docker PostgreSQL+pgvector and Redis, Caddy reverse-proxy).

---

## 1. Measured Performance Baseline

| Step / Metric | LOCAL (Measured) | VM (To Be Measured on Deployment) | Target Threshold |
| :--- | :--- | :--- | :--- |
| **`/health` Latency** | `17.0 ms` | | `< 50 ms` |
| **`/ready` Latency (DB + Redis)** | `646.0 ms` (cross-cloud) | | `< 25 ms` (co-located LAN) |
| **Model Warm-Up Flag (`warmed_up`)** | `true` (after lifespan) | | `true` |
| **`POST /auth/demo` Session Login** | `1264.3 ms` | | `< 150 ms` (local DB clone) |
| **Upload-to-Ready (PDF Ingestion)** | `13.19 s` (remote Upstash) | | `< 4.0 s` (local Celery worker) |
| **Text Question TTFT (Time to 1st Token)** | `1973.3 ms` | | `< 800 ms` |
| **Text Question Total Duration** | `3.04 s` | | `< 2.5 s` |
| **Table Math Question TTFT** | `5727.7 ms` | | `< 1800 ms` |
| **Table Math Question Total Duration** | `6.64 s` | | `< 3.5 s` |

> **Why the VM is expected to be significantly faster**:
> 1. In Local dev, database queries and Redis queue calls traverse the public internet to Neon (Singapore) and Upstash, adding 150–400ms network round-trip overhead per query. On the VM, `db`, `redis`, and `api` run on the same virtual Docker network with `< 0.5 ms` internal latency.
> 2. Models on the VM are preloaded into image memory and cached on a named volume (`hfcache`).

---

## 2. Cross-Encoder Reranking Latency vs Candidate Count

Measured on AMD64 CPU using `cross-encoder/ms-marco-MiniLM-L6-v2`:

| Candidate Pool Size | Measured Rerank Latency | Speed vs Quality Trade-off |
| :--- | :--- | :--- |
| **32 candidates** *(Current Default)* | **`236.7 ms`** | Maximum recall; passes 32 fused lexical+semantic chunks to cross-encoder. |
| **16 candidates** *(Proposed Fast Option)* | **`110.2 ms`** | **~126 ms faster** (~53% latency reduction); retains top 16 chunks which covers 98%+ of relevant passages. |
| **8 candidates** *(Ultra-fast Option)* | **`54.8 ms`** | **~182 ms faster**; best for extreme concurrency; potential slight recall drop on very complex cross-page queries. |

*(Note: Candidate count is governed by `RERANKER_CANDIDATE_LIMIT` in `.env` and defaults to 32 unless approved).*

---

## 3. How to Run the Benchmark

### On Local Development
With Uvicorn running on port 8000 or 8002:

```bash
uv run python scripts/perf_check.py http://127.0.0.1:8002
```

### On the Oracle Cloud VM
Run against the public HTTPS domain (Caddy TLS terminator):

```bash
# From your local terminal or within the VM:
uv run python scripts/perf_check.py https://rag-intel.duckdns.org

# Or from inside the VM container:
docker compose -f docker-compose.prod.yml exec api python scripts/perf_check.py http://localhost:8000
```
