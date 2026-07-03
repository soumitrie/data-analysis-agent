"""Aggregated profiling for the LLM.

`build_profile` returns the LLMProfile — the ONLY object that may reach Gemini.
It contains column schema/types/cardinalities, row count, date range, amount
summary statistics, and top-K category labels with aggregated totals. No raw
transaction row or raw cell value (beyond category *labels*) is ever included.

All aggregation is vectorized pandas (describe / groupby / value_counts) — O(n)
passes, never per-row Python loops — so it scales to ~1M rows.
"""
from __future__ import annotations

import math

import pandas as pd
from pandas.api import types as pdt

from analysis import columns as col_detect

TOP_K_CATEGORIES = 12


def _clean_float(value) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(f) or math.isinf(f):
        return 0.0
    return f


def _dtype_label(series: pd.Series) -> str:
    if pdt.is_numeric_dtype(series):
        return str(series.dtype)
    if pdt.is_datetime64_any_dtype(series):
        return "datetime"
    return "string"


def _date_range(df: pd.DataFrame, date_col: str | None) -> dict:
    if not date_col:
        return {"start": None, "end": None}
    parsed = pd.to_datetime(df[date_col], errors="coerce", format="mixed").dropna()
    if parsed.empty:
        return {"start": None, "end": None}
    return {
        "start": parsed.min().date().isoformat(),
        "end": parsed.max().date().isoformat(),
    }


def _amount_summary(df: pd.DataFrame, amount_col: str | None) -> dict | None:
    if not amount_col:
        return None
    series = pd.to_numeric(df[amount_col], errors="coerce").dropna()
    if series.empty:
        return None
    q = series.quantile([0.25, 0.5, 0.75])
    return {
        "sum": _clean_float(series.sum()),
        "mean": _clean_float(series.mean()),
        "min": _clean_float(series.min()),
        "max": _clean_float(series.max()),
        "q1": _clean_float(q.loc[0.25]),
        "median": _clean_float(q.loc[0.5]),
        "q3": _clean_float(q.loc[0.75]),
    }


def _top_categories(df: pd.DataFrame, category_col: str | None, amount_col: str | None) -> list[dict]:
    if not category_col:
        return []
    if amount_col:
        amounts = pd.to_numeric(df[amount_col], errors="coerce")
        grp = pd.DataFrame({"cat": df[category_col], "amt": amounts}).dropna(subset=["cat"])
        agg = grp.groupby("cat")["amt"].agg(total="sum", count="count")
        agg = agg.reindex(agg["total"].abs().sort_values(ascending=False).index)
    else:
        counts = df[category_col].value_counts(dropna=True)
        agg = pd.DataFrame({"total": 0.0, "count": counts})
    out = []
    for label, row in agg.head(TOP_K_CATEGORIES).iterrows():
        out.append({
            "label": str(label),
            "total": _clean_float(row["total"]),
            "count": int(row["count"]),
        })
    return out


def build_profile(df: pd.DataFrame) -> dict:
    date_col = col_detect.pick_date_column(df)
    amount_col = col_detect.pick_amount_column(df, exclude={date_col} if date_col else set())
    category_col = col_detect.pick_category_column(
        df, exclude={c for c in (date_col, amount_col) if c}
    )

    columns = [
        {
            "name": str(name),
            "dtype": _dtype_label(df[name]),
            "cardinality": int(df[name].nunique(dropna=True)),
            "role": None,
        }
        for name in df.columns
    ]

    return {
        "row_count": int(len(df)),
        "columns": columns,
        "date_range": _date_range(df, date_col),
        "amount_summary": _amount_summary(df, amount_col),
        "top_categories": _top_categories(df, category_col, amount_col),
    }


def apply_roles(profile: dict, mapping: dict) -> dict:
    """Annotate profile columns with detected roles (in place) and return it."""
    role_by_name = {
        mapping.get("date"): "date",
        mapping.get("amount"): "amount",
        mapping.get("category"): "category",
        mapping.get("counterparty"): "counterparty",
    }
    for col in profile.get("columns", []):
        col["role"] = role_by_name.get(col["name"])
    return profile
