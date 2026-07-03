"""Aggregated data-table serializer.

Every chart carries the exact aggregated table it plotted (bucket-level rows +
column header labels). The `/charts/{cid}/table` endpoint serves this same table,
so the figure and the table can never disagree. Raw transaction rows never appear
here — only aggregated buckets.
"""
from __future__ import annotations

import math
from typing import Any


def _cell(value: Any) -> Any:
    """Coerce one cell to a JSON-safe scalar (str | int | float)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int,)):
        return int(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return 0.0
        return float(value)
    # numpy scalars expose .item()
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _cell(item())
        except Exception:  # pragma: no cover - defensive
            pass
    return str(value)


def make_table(columns: list[str], rows: list[list[Any]]) -> dict:
    """Build a {columns, rows} table with JSON-safe, header-labelled cells.

    `columns` are the human-readable header labels; `rows` is a list of equal-length
    lists of bucket-level values (never raw transaction rows)."""
    clean_cols = [str(c) for c in columns]
    clean_rows = [[_cell(v) for v in row] for row in rows]
    return {"columns": clean_cols, "rows": clean_rows}
