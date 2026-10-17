"""Script to generate realistic sample PDFs for demo mode.

Generates:
1. samples/rag_architecture_guide.pdf: Text-heavy PDF detailing modern RAG systems.
2. samples/quarterly_financial_report.pdf: Document containing explicit bordered tables
   with numeric quarterly metrics for table analytics testing.
"""
from pathlib import Path
import fitz  # PyMuPDF
import pdfplumber

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def create_rag_guide_pdf(output_path: Path):
    doc = fitz.open()
    
    # Page 1: Architecture & Ingestion
    page1 = doc.new_page(width=595, height=842)  # A4
    text1 = """RAG Architecture & Document Intelligence Guide

1. Executive Summary
Retrieval-Augmented Generation (RAG) significantly improves LLM responses by conditioning generation on authoritative local document context. In enterprise environments, document intelligence systems must handle heterogeneous documents (PDFs, multi-column layouts, tables, and scanned receipts) while maintaining strict citation grounding and low latency.

2. Document Ingestion Pipeline
The document ingestion process begins with structural document parsing. Using PyMuPDF for native vector text and pdfplumber for coordinate-aware table boundary detection, documents are decomposed into semantic units. Scanned pages or rasterized diagrams trigger optical character recognition (OCR) via Tesseract with image preprocessing.

3. Chunking Strategies and Granularity
Fixed character chunking often fractures important context. To mitigate this, recursive character splitting uses structural delimiters (headings, double newlines, sentence terminators). Chunks are targeted at 800 to 1200 characters with a 150-character sliding overlap to ensure boundary continuity across chunk transitions.

4. Hybrid Representation: Dense Vector & Sparse Lexical
Each text chunk receives dual representations:
- Dense Embeddings: Generated using BAAI/bge-small-en-v1.5 and indexed in PostgreSQL using pgvector (HNSW / IVFFlat).
- Sparse Inverted Index: Computed using PostgreSQL to_tsvector and tsquery for exact keyword, acronym, and entity recall.
"""
    rect1 = fitz.Rect(50, 50, 545, 800)
    page1.insert_textbox(rect1, text1, fontsize=11, fontname="helv")

    # Page 2: Retrieval, Fusion, & LangGraph Workflow
    page2 = doc.new_page(width=595, height=842)
    text2 = """5. Reciprocal Rank Fusion (RRF) & Re-ranking
Because dense similarity scores (cosine distance) and sparse BM25 scores (term frequencies) operate on disparate numerical scales, Reciprocal Rank Fusion (RRF) combines ranked lists without manual weight tuning:
RRF_score(d) = sum(1.0 / (k + rank_i(d))) where k is set to 60.

Top candidates from RRF fusion then undergo cross-encoder re-ranking using a cross-attention transformer (e.g. ms-marco-MiniLM-L-6-v2). The cross-encoder jointly computes token interactions between query and candidate chunks, filtering out false positives.

6. Agentic Orchestration with LangGraph
A stateful LangGraph workflow routes queries dynamically:
- Direct Answer: Fact-based questions with high retrieval confidence.
- Query Rewriting: Reformulates ambiguous or short queries into targeted retrieval keys.
- Table Analytics Mode: Directly routes questions about numerical aggregations to the deterministic tabular compute engine.
- Citation Alignment: Every claim maps back to verifiable page numbers and chunk hashes for strict verification.
"""
    rect2 = fitz.Rect(50, 50, 545, 800)
    page2.insert_textbox(rect2, text2, fontsize=11, fontname="helv")

    doc.save(str(output_path))
    doc.close()
    print(f"Generated text PDF: {output_path}")


def create_financial_report_pdf(output_path: Path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    title = """TechCorp Solutions — Fiscal Year 2025 Financial Performance

Executive Overview:
This report outlines the quarterly operational and cloud infrastructure spend across FY2025.
The table below details quarterly revenue, operating expenses, cloud compute hosting,
research & development (R&D), and net income in millions of USD ($M).
"""
    rect_title = fitz.Rect(50, 50, 545, 175)
    page.insert_textbox(rect_title, title, fontsize=11, fontname="helv")

    # Draw a table with explicit lines and cell text
    # Table layout:
    # Columns: Metric, Q1, Q2, Q3, Q4, FY2025 Total
    x_start = 50
    y_start = 180
    col_widths = [140, 60, 60, 60, 60, 95]
    row_height = 25

    table_data = [
        ["Metric ($M)", "Q1", "Q2", "Q3", "Q4", "Total"],
        ["Revenue", "120.5", "135.2", "148.0", "165.8", "569.5"],
        ["Cloud Hosting", "14.2", "15.0", "16.8", "12.4", "58.4"],
        ["R&D Expenses", "32.0", "34.5", "38.2", "41.0", "145.7"],
        ["Operating Costs", "45.0", "48.2", "50.1", "52.3", "195.6"],
        ["Net Income", "29.3", "37.5", "42.9", "60.1", "169.8"],
    ]

    # Draw grid lines
    num_rows = len(table_data)
    total_width = sum(col_widths)
    total_height = num_rows * row_height

    # Horizontal lines
    for i in range(num_rows + 1):
        y = y_start + i * row_height
        page.draw_line(fitz.Point(x_start, y), fitz.Point(x_start + total_width, y), color=(0.2, 0.2, 0.2), width=1)

    # Vertical lines
    curr_x = x_start
    for width in [0] + col_widths:
        curr_x += width
        page.draw_line(fitz.Point(curr_x, y_start), fitz.Point(curr_x, y_start + total_height), color=(0.2, 0.2, 0.2), width=1)

    # Insert cell texts
    curr_y = y_start
    for r_idx, row in enumerate(table_data):
        curr_x = x_start
        for c_idx, cell in enumerate(row):
            font = "hebo" if r_idx == 0 or c_idx == 0 else "helv"
            rect = fitz.Rect(curr_x + 4, curr_y + 4, curr_x + col_widths[c_idx] - 4, curr_y + row_height - 4)
            page.insert_textbox(rect, cell, fontsize=10, fontname=font, align=fitz.TEXT_ALIGN_LEFT)
            curr_x += col_widths[c_idx]
        curr_y += row_height

    # Analysis summary below the table
    summary_text = """Key Highlights:
- Q4 achieved the highest quarterly revenue ($165.8M) and net income ($60.1M).
- Cloud hosting expenses dropped from $16.8M in Q3 to $12.4M in Q4 following ARM VM migration.
- Total FY2025 net income reached $169.8M, representing a 28% year-over-year increase.
- Research and Development (R&D) investments scaled from $32.0M in Q1 to $41.0M in Q4.
"""
    rect_sum = fitz.Rect(50, curr_y + 20, 545, 800)
    page.insert_textbox(rect_sum, summary_text, fontsize=10, fontname="helv")

    doc.save(str(output_path))
    doc.close()
    print(f"Generated table PDF: {output_path}")


if __name__ == "__main__":
    p1 = SAMPLES_DIR / "rag_architecture_guide.pdf"
    p2 = SAMPLES_DIR / "quarterly_financial_report.pdf"
    create_rag_guide_pdf(p1)
    create_financial_report_pdf(p2)

    # Verify table extraction with pdfplumber
    with pdfplumber.open(str(p2)) as pdf:
        tables = pdf.pages[0].extract_tables()
        print(f"Verified pdfplumber tables in financial PDF: {len(tables)} table(s) found.")
        for t in tables:
            for row in t:
                print("  ", row)
