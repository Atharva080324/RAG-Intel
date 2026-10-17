#!/usr/bin/env python
"""Seed script for the demo mode.

Usage (run after `alembic upgrade head`):
    DEMO_MODE=true python scripts/seed_demo.py

What it does
------------
1. Calls POST /auth/demo to obtain a JWT for the shared demo user.
2. Uploads the PDF files found in ``samples/`` into that user's account.
3. Polls each ingestion job until it reaches ``completed`` or ``failed``.
4. Displays 4-5 suggested questions per file (including table math: sum/avg/max).

Environment variables
---------------------
- API_BASE       : Base URL of the running API (default: http://127.0.0.1:8000).
- DEMO_MODE      : Must be "true" (the script checks this before making network calls).
- POLL_TIMEOUT_S : Seconds to wait per document (default: 120).
"""
import os
import sys
import time
import mimetypes
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("httpx is required: pip install httpx")

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower()
POLL_TIMEOUT = int(os.environ.get("POLL_TIMEOUT_S", "120"))
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"

SUGGESTED_QUESTIONS = {
    "rag_architecture_guide.pdf": [
        "How does Reciprocal Rank Fusion (RRF) combine dense and sparse retrieval scores?",
        "What chunking strategy and overlap size are used during document ingestion?",
        "Why is cross-encoder re-ranking applied after initial candidate retrieval?",
        "How does LangGraph dynamically route queries between direct answer and table analytics?",
        "What embedding model is used for dense vector representation in PostgreSQL?",
    ],
    "quarterly_financial_report.pdf": [
        "What was the total revenue across all four quarters of FY2025?",
        "What was the average quarterly cloud hosting expense in FY2025?",
        "Which quarter achieved the maximum net income, and what was the value?",
        "What were the operating costs in Q3 compared to Q4?",
        "By what percentage did total FY2025 net income increase year-over-year?",
    ],
}


def main() -> None:
    if DEMO_MODE != "true":
        sys.exit(
            "DEMO_MODE is not set to 'true'. "
            "Export DEMO_MODE=true before running this script."
        )

    samples = sorted(SAMPLES_DIR.glob("*.pdf"))
    if not samples:
        sys.exit(
            f"No PDF files found in {SAMPLES_DIR}. "
            "Run `python scripts/create_sample_pdfs.py` to generate sample PDFs."
        )

    print(f"API  : {API_BASE}")
    print(f"Files: {[f.name for f in samples]}\n")

    # ── 1. Obtain demo JWT ────────────────────────────────────────────────────
    with httpx.Client(base_url=API_BASE, timeout=30) as client:
        r = client.post("/auth/demo")
        if r.status_code != 200:
            sys.exit(f"POST /auth/demo failed ({r.status_code}): {r.text}")
        token = r.json()["access_token"]
        print(f"✓  Demo JWT obtained (expires_in={r.json()['expires_in']}s)\n")

        headers = {"Authorization": f"Bearer {token}"}

        # ── 2. Upload each file ───────────────────────────────────────────────
        jobs: list[dict] = []
        for path in samples:
            mime = mimetypes.guess_type(path.name)[0] or "application/pdf"
            with path.open("rb") as fh:
                ur = client.post(
                    "/documents/upload",
                    files={"file": (path.name, fh, mime)},
                    headers=headers,
                )
            if ur.status_code == 202:
                j = ur.json()
                print(f"✓  Uploaded {path.name} → job {j['job_id']} doc {j['document_id']}")
                j["filename"] = path.name
                jobs.append(j)
            elif ur.status_code == 409:
                print(f"~  {path.name} already uploaded (409 duplicate) — skipping")
            else:
                print(f"✗  {path.name} upload failed ({ur.status_code}): {ur.text}")

        # ── 3. Poll until done ────────────────────────────────────────────────
        print()
        for j in jobs:
            job_id = j["job_id"]
            deadline = time.time() + POLL_TIMEOUT
            while time.time() < deadline:
                pr = client.get(f"/jobs/{job_id}", headers=headers)
                if pr.status_code != 200:
                    print(f"✗  Job {job_id}: poll error {pr.status_code}")
                    break
                data = pr.json()
                st = data.get("status", "unknown")
                if st == "completed":
                    print(f"✓  Job {job_id} ({j.get('filename')}) completed (progress={data.get('progress')}%)")
                    break
                if st == "failed":
                    print(f"✗  Job {job_id} failed: {data.get('error_message')}")
                    break
                print(f"   Job {job_id} status={st} progress={data.get('progress')}%", end="\r")
                time.sleep(3)
            else:
                print(f"✗  Job {job_id} timed out after {POLL_TIMEOUT}s")

    print("\n" + "=" * 70)
    print("Seed complete! Suggested Questions for Recruiter Showcase:")
    print("=" * 70)
    for fname, questions in SUGGESTED_QUESTIONS.items():
        print(f"\nDocument: {fname}")
        for idx, q in enumerate(questions, 1):
            print(f"  {idx}. {q}")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
