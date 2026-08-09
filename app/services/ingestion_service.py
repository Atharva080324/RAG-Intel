"""Phase 2 extraction, structure preservation, chunking, and embeddings."""
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import fitz
import pdfplumber
from huggingface_hub import InferenceClient

from app.core.config import settings

_embedding_client: InferenceClient | None = None


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    tables: list[str]


def _table_markdown(rows: list[list[object | None]]) -> str:
    clean = [[str(cell or "").replace("\n", " ").strip() for cell in row] for row in rows if row]
    if not clean:
        return ""
    width = max(len(row) for row in clean)
    clean = [row + [""] * (width - len(row)) for row in clean]
    header = clean[0]
    return "| " + " | ".join(header) + " |\n| " + " | ".join(["---"] * width) + " |\n" + "\n".join("| " + " | ".join(row) + " |" for row in clean[1:])


def extract_pdf(path: str) -> list[ExtractedPage]:
    document = fitz.open(path)
    table_pages: dict[int, list[str]] = {}
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            table_pages[number] = [markdown for table in page.extract_tables() if (markdown := _table_markdown(table))]
    extracted: list[ExtractedPage] = []
    for number, page in enumerate(document, start=1):
        text = page.get_text("text").strip()
        if not text:
            # Tesseract is optional at runtime; a missing binary is a recoverable extraction failure.
            try:
                import pytesseract
                from PIL import Image
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
                text = pytesseract.image_to_string(image).strip()
            except Exception:
                text = ""
        extracted.append(ExtractedPage(number, text, table_pages.get(number, [])))
    return extracted


def extract_text(path: str) -> list[ExtractedPage]:
    return [ExtractedPage(1, Path(path).read_text(encoding="utf-8", errors="replace"), [])]


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> Iterable[str]:
    text = " ".join(text.split())
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        if end < len(text):
            end = max(text.rfind(". ", start, end) + 1, text.rfind(" ", start, end)) or end
        yield text[start:end].strip()
        if end == len(text):
            break
        start = max(end - overlap, start + 1)


def embed(texts: list[str], *, is_query: bool = False) -> list[list[float]]:
    """Hosted BGE embeddings; no embedding model weights are loaded by this service."""
    global _embedding_client
    if not settings.hf_token:
        raise RuntimeError("HF_TOKEN is required for hosted embeddings")
    if _embedding_client is None:
        _embedding_client = InferenceClient(provider="hf-inference", api_key=settings.hf_token)
    inputs = texts
    if is_query:
        inputs = [f"Represent this sentence for searching relevant passages: {text}" for text in texts]
    vectors = _embedding_client.feature_extraction(inputs, model=settings.embedding_model, normalize=True)
    result = vectors.tolist() if hasattr(vectors, "tolist") else vectors
    if any(len(vector) != settings.embedding_dimension for vector in result):
        raise RuntimeError("Embedding provider returned an unexpected vector dimension")
    return result
