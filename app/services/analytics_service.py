from __future__ import annotations

import re
from io import StringIO
from typing import Any

from app.models.chunk import Chunk


def _markdown_to_dataframe(markdown: str):
    import pandas as pd

    lines = [line.strip() for line in markdown.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        raise ValueError("Retrieved content is not a markdown table")
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines]
    headers = rows[0]
    data_rows = [row for row in rows[2:] if not all(set(cell) <= {"-", ":", " "} for cell in row)]
    width = len(headers)
    frame = pd.DataFrame([row[:width] + [""] * max(0, width - len(row)) for row in data_rows], columns=headers)
    for column in frame.columns:
        converted = pd.to_numeric(frame[column].str.replace(",", "", regex=False).str.replace("%", "", regex=False), errors="coerce")
        if converted.notna().any():
            frame[column] = converted
    return frame


def _requested_operation(question: str) -> str:
    lowered = question.lower()
    if "average" in lowered or "mean" in lowered:
        return "mean"
    if "sum" in lowered or "total" in lowered:
        return "sum"
    if "maximum" in lowered or "highest" in lowered or "largest" in lowered:
        return "max"
    if "minimum" in lowered or "lowest" in lowered or "smallest" in lowered:
        return "min"
    raise ValueError("Supported table operations are average, sum, maximum, and minimum")


def analyze_table_question(question: str, table_chunks: list[Chunk]) -> dict[str, Any]:
    if not table_chunks:
        raise ValueError("No table was retrieved for this question")
    frame = _markdown_to_dataframe(table_chunks[0].content)
    numeric_columns = list(frame.select_dtypes(include="number").columns)
    if not numeric_columns:
        raise ValueError("Retrieved table has no numeric columns")
    requested_column = next((column for column in frame.columns if column.lower() in question.lower()), None)
    column = requested_column if requested_column in numeric_columns else numeric_columns[0]
    operation = _requested_operation(question)
    value = getattr(frame[column], operation)()
    if hasattr(value, "item"):
        value = value.item()
    return {
        "operation": operation,
        "column": column,
        "value": value,
        "rows_used": int(len(frame)),
        "source_chunk_id": table_chunks[0].id,
    }
