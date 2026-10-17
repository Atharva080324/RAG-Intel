#!/usr/bin/env python
"""Performance verification script for RAG Document Intelligence.

Measures:
  1. /health latency
  2. /ready latency and warm-up status
  3. POST /auth/demo session login latency
  4. Upload-to-completed ingestion latency (PyMuPDF -> chunk -> embed -> pgvector)
  5. Text question: Time To First Token (TTFT) & Total streaming duration
  6. Table question: Time To First Token (TTFT) & Total streaming duration

Usage:
  # Local test:
  python scripts/perf_check.py http://127.0.0.1:8002

  # Remote VM test:
  python scripts/perf_check.py https://rag-intel.duckdns.org
"""
import argparse
import json
import mimetypes
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("httpx is required: uv run pip install httpx")

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
SAMPLE_PDF = SAMPLES_DIR / "quarterly_financial_report.pdf"


def run_benchmark(base_url: str):
    base_url = base_url.rstrip("/")
    print(f"\n========================================================")
    print(f" RAGINTEL Performance Benchmark: {base_url}")
    print(f"========================================================\n")

    results = {}

    with httpx.Client(timeout=60.0) as client:
        # ── 1. Health check ──────────────────────────────────────────────────
        print("[1/6] Measuring /health latency...")
        t0 = time.perf_counter()
        r_health = client.get(f"{base_url}/health")
        t_health = (time.perf_counter() - t0) * 1000
        if r_health.status_code != 200:
            sys.exit(f"FAILED /health: status {r_health.status_code}")
        results["health_ms"] = round(t_health, 1)
        print(f"      -> {t_health:.1f} ms (status: {r_health.json().get('status')})")

        # ── 2. Readiness check ───────────────────────────────────────────────
        print("[2/6] Measuring /ready latency & warm-up status...")
        t0 = time.perf_counter()
        r_ready = client.get(f"{base_url}/ready")
        t_ready = (time.perf_counter() - t0) * 1000
        if r_ready.status_code != 200:
            print(f"      WARNING: /ready returned {r_ready.status_code}")
        ready_data = r_ready.json()
        results["ready_ms"] = round(t_ready, 1)
        results["warmed_up"] = ready_data.get("warmed_up", False)
        print(f"      -> {t_ready:.1f} ms (warmed_up: {results['warmed_up']}, status: {ready_data.get('status')})")

        # ── 3. Demo Login ────────────────────────────────────────────────────
        print("[3/6] Measuring POST /auth/demo session login latency...")
        t0 = time.perf_counter()
        r_demo = client.post(f"{base_url}/auth/demo")
        t_demo = (time.perf_counter() - t0) * 1000
        if r_demo.status_code != 200:
            sys.exit(f"FAILED /auth/demo ({r_demo.status_code}): {r_demo.text}")
        token_data = r_demo.json()
        token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        results["demo_login_ms"] = round(t_demo, 1)
        print(f"      -> {t_demo:.1f} ms (JWT obtained)")

        # ── 4. Upload & Ingestion ────────────────────────────────────────────
        print("[4/6] Measuring document upload-to-completed latency...")
        if not SAMPLE_PDF.exists():
            sys.exit(f"Sample PDF not found at {SAMPLE_PDF}")

        mime = mimetypes.guess_type(SAMPLE_PDF.name)[0] or "application/pdf"
        t0 = time.perf_counter()
        with SAMPLE_PDF.open("rb") as f:
            r_upload = client.post(
                f"{base_url}/documents/upload",
                files={"file": (SAMPLE_PDF.name, f, mime)},
                headers=headers,
            )
        if r_upload.status_code not in (200, 202, 409):
            sys.exit(f"FAILED upload ({r_upload.status_code}): {r_upload.text}")

        upload_data = r_upload.json()
        doc_id = upload_data.get("document_id")
        job_id = upload_data.get("job_id")

        if r_upload.status_code == 409 or not job_id:
            # Document already existed; retrieve document id from list
            r_list = client.get(f"{base_url}/documents/", headers=headers)
            items = r_list.json().get("items", [])
            doc_id = items[0]["id"] if items else None
            t_ingest = time.perf_counter() - t0
            print(f"      -> Document already pre-seeded/completed in {t_ingest:.2f}s (doc #{doc_id})")
            results["ingest_s"] = round(t_ingest, 2)
        else:
            # Poll job
            status_val = "queued"
            while time.perf_counter() - t0 < 60:
                time.sleep(0.5)
                r_job = client.get(f"{base_url}/jobs/{job_id}", headers=headers)
                if r_job.status_code == 200:
                    status_val = r_job.json().get("status")
                    if status_val in ("completed", "failed"):
                        break
            t_ingest = time.perf_counter() - t0
            if status_val != "completed":
                print(f"      WARNING: Ingestion ended with status: {status_val}")
            results["ingest_s"] = round(t_ingest, 2)
            print(f"      -> Ingestion completed in {t_ingest:.2f}s (job #{job_id}, doc #{doc_id})")

        # ── 5. Text Question Streaming ───────────────────────────────────────
        print("[5/6] Measuring text question streaming & TTFT...")
        text_q = "What is the primary content and structure of this report?"
        ttft, total_time, chunks_received = stream_question(base_url, headers, doc_id, text_q)
        results["text_ttft_ms"] = round(ttft, 1)
        results["text_total_s"] = round(total_time, 2)
        print(f"      -> TTFT: {ttft:.1f} ms | Total: {total_time:.2f}s ({chunks_received} tokens received)")

        # ── 6. Table Math Question Streaming ─────────────────────────────────
        print("[6/6] Measuring table math question streaming & TTFT...")
        table_q = "What was the total revenue across all four quarters of FY2025?"
        ttft, total_time, chunks_received = stream_question(base_url, headers, doc_id, table_q)
        results["table_ttft_ms"] = round(ttft, 1)
        results["table_total_s"] = round(total_time, 2)
        print(f"      -> TTFT: {ttft:.1f} ms | Total: {total_time:.2f}s ({chunks_received} tokens received)")

    print_summary(results, base_url)


def stream_question(base_url: str, headers: dict, doc_id: int, question: str):
    url = f"{base_url}/questions/stream"
    payload = {"document_id": doc_id, "question": question}
    t_start = time.perf_counter()
    ttft = None
    chunks_count = 0

    with httpx.stream("POST", url, json=payload, headers=headers, timeout=60.0) as response:
        if response.status_code != 200:
            raise RuntimeError(f"Stream request failed: {response.status_code} {response.read().decode()}")

        for line in response.iter_lines():
            if not line:
                continue
            if line.startswith("data: "):
                data_str = line[6:]
                if ttft is None:
                    ttft = (time.perf_counter() - t_start) * 1000
                chunks_count += 1
                try:
                    data = json.loads(data_str)
                    if data.get("type") == "done":
                        break
                except Exception:
                    pass

    total_duration = time.perf_counter() - t_start
    return ttft or 0.0, total_duration, chunks_count


def print_summary(res: dict, base_url: str):
    print("\n" + "=" * 60)
    print("                BENCHMARK RESULTS TABLE")
    print("=" * 60)
    print(f"Target URL: {base_url}")
    print("-" * 60)
    print(f"{'Metric':<38} | {'Measured Value':<18}")
    print("-" * 60)
    print(f"{'/health Latency':<38} | {res.get('health_ms')} ms")
    print(f"{'/ready Latency':<38} | {res.get('ready_ms')} ms")
    print(f"{'Model Warm-Up Flag (warmed_up)':<38} | {res.get('warmed_up')}")
    print(f"{'POST /auth/demo Session Login':<38} | {res.get('demo_login_ms')} ms")
    print(f"{'Document Upload-to-Ready Time':<38} | {res.get('ingest_s')} s")
    print(f"{'Text Question TTFT':<38} | {res.get('text_ttft_ms')} ms")
    print(f"{'Text Question Total Time':<38} | {res.get('text_total_s')} s")
    print(f"{'Table Math Question TTFT':<38} | {res.get('table_ttft_ms')} ms")
    print(f"{'Table Math Question Total Time':<38} | {res.get('table_total_s')} s")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG Document Intelligence Performance Benchmark")
    parser.add_argument("url", nargs="?", default="http://127.0.0.1:8002", help="Base URL of the API")
    args = parser.parse_args()
    run_benchmark(args.url)
