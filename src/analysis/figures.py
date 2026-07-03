"""Deterministic figure computation.

Every displayed number is computed here, by pandas, over the FULL DataFrame —
never sampled, never produced by the LLM. Each chart returns a complete Plotly
figure (data + layout) with the IB house style already applied server-side.

The LLM only chooses *which* chart types and labels; this module owns all math.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from analysis import housestyle

WHITELIST = {"time_series", "top_n_breakdown", "distribution"}
DEFAULT_TOP_N = 10


# ---------- helpers ----------

def _amount_series(df: pd.DataFrame, amount_col: str) -> pd.Series:
    return pd.to_numeric(df[amount_col], errors="coerce")


def _bucket_freq(span_days: int) -> tuple[str, str]:
    """Choose a time bucket from the date span. Returns (pandas_freq, label)."""
    if span_days <= 31:
        return "D", "Daily"
    if span_days <= 180:
        return "W-MON", "Weekly"
    return "ME", "Monthly"


# ---------- chart types ----------

def _time_series(df: pd.DataFrame, spec: dict, mapping: dict) -> dict:
    date_col = mapping.get("date")
    amount_col = mapping.get("amount")
    if not date_col or not amount_col:
        raise ValueError("time_series requires both a date and an amount column")

    work = pd.DataFrame({
        "date": pd.to_datetime(df[date_col], errors="coerce", format="mixed"),
        "amount": _amount_series(df, amount_col),
    }).dropna(subset=["date"])
    if work.empty:
        raise ValueError("no parseable dates for time_series")

    span_days = int((work["date"].max() - work["date"].min()).days)
    freq, label = _bucket_freq(span_days)
    series = work.set_index("date")["amount"].resample(freq).sum()

    x = [ts.date().isoformat() for ts in series.index]
    y = [float(v) for v in series.values]
    total = float(work["amount"].sum())

    fig = go.Figure(
        go.Scatter(
            x=x, y=y, mode="lines+markers",
            line=dict(color=housestyle.NAVY, width=2.5),
            marker=dict(color=housestyle.NAVY, size=6),
            fill="tozeroy", fillcolor="rgba(27,42,65,0.06)",
            hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>",
        )
    )
    housestyle.apply_house_style(
        fig,
        title=spec.get("title") or "Total Transaction Value Over Time",
        subtitle=spec.get("subtitle") or f"{label} · sum of amount",
        x_title="Period",
        y_title="Total value",
        value_axis="y",
    )
    return {
        "type": "time_series",
        "title": spec.get("title") or "Total Transaction Value Over Time",
        "subtitle": spec.get("subtitle") or f"{label} · sum of amount",
        "figure": fig.to_plotly_json(),
        "computed_summary": {"total": total, "n_buckets": int(len(series))},
        "rationale": spec.get("rationale")
        or f"The dataset spans ~{span_days} days; a {label.lower()} trend shows value flow over time.",
    }


def _top_n_breakdown(df: pd.DataFrame, spec: dict, mapping: dict) -> dict:
    amount_col = mapping.get("amount")
    group_role = spec.get("group_role")
    group_col = None
    if group_role in ("counterparty", "category"):
        group_col = mapping.get(group_role)
    if not group_col:
        group_col = mapping.get("counterparty") or mapping.get("category")
    if not amount_col or not group_col:
        raise ValueError("top_n_breakdown requires an amount and a grouping column")

    top_n = int(spec.get("top_n") or DEFAULT_TOP_N)
    work = pd.DataFrame({
        "group": df[group_col],
        "amount": _amount_series(df, amount_col),
    }).dropna(subset=["group"])
    totals = work.groupby("group")["amount"].sum()
    if totals.empty:
        raise ValueError("no groups to aggregate for top_n_breakdown")

    ranked = totals.reindex(totals.abs().sort_values(ascending=False).index)
    top = ranked.head(top_n)
    denom = float(totals.abs().sum())
    covered_share = float(top.abs().sum() / denom) if denom else 0.0

    # Horizontal bars, largest at top
    labels = [str(i) for i in top.index][::-1]
    values = [float(v) for v in top.values][::-1]

    fig = go.Figure(
        go.Bar(
            x=values, y=labels, orientation="h",
            marker=dict(color=housestyle.NAVY),
            hovertemplate="%{y}<br>%{x:,.2f}<extra></extra>",
        )
    )
    housestyle.apply_house_style(
        fig,
        title=spec.get("title") or f"Top {group_col.title()} by Total Value",
        subtitle=spec.get("subtitle") or f"Top {len(top)} · sum of amount",
        x_title="Total value",
        y_title="",
        value_axis="x",
    )
    return {
        "type": "top_n_breakdown",
        "title": spec.get("title") or f"Top {group_col.title()} by Total Value",
        "subtitle": spec.get("subtitle") or f"Top {len(top)} · sum of amount",
        "figure": fig.to_plotly_json(),
        "computed_summary": {
            "top_n": int(len(top)),
            "covered_share": round(covered_share, 4),
            "group_by": group_col,
        },
        "rationale": spec.get("rationale")
        or f"Value is concentrated among a few {group_col} — the top {len(top)} cover "
        f"{covered_share:.0%} of gross value.",
    }


def _n_bins(n: int) -> int:
    if n <= 1:
        return 1
    return int(min(80, max(20, round(math.sqrt(n)))))


def _distribution(df: pd.DataFrame, spec: dict, mapping: dict) -> dict:
    amount_col = mapping.get("amount")
    if not amount_col:
        raise ValueError("distribution requires an amount column")

    amounts = _amount_series(df, amount_col).dropna()
    if amounts.empty:
        raise ValueError("no numeric amounts for distribution")

    nbins = int(spec.get("n_bins") or _n_bins(len(amounts)))
    counts, edges = np.histogram(amounts.to_numpy(), bins=nbins)
    centers = [float((edges[i] + edges[i + 1]) / 2) for i in range(len(counts))]
    width = float(edges[1] - edges[0]) if len(edges) > 1 else 1.0

    fig = go.Figure(
        go.Bar(
            x=centers, y=[int(c) for c in counts],
            width=width * 0.95,
            marker=dict(color=housestyle.ACCENT),
            hovertemplate="~%{x:,.2f}<br>%{y:,} txns<extra></extra>",
        )
    )
    housestyle.apply_house_style(
        fig,
        title=spec.get("title") or "Distribution of Transaction Sizes",
        subtitle=spec.get("subtitle") or f"Histogram · {nbins} bins",
        x_title="Transaction amount",
        y_title="Number of transactions",
        value_axis="y",
    )
    return {
        "type": "distribution",
        "title": spec.get("title") or "Distribution of Transaction Sizes",
        "subtitle": spec.get("subtitle") or f"Histogram · {nbins} bins",
        "figure": fig.to_plotly_json(),
        "computed_summary": {"n_bins": nbins, "total_count": int(len(df))},
        "rationale": spec.get("rationale")
        or "Reveals the spread and tail of individual transaction amounts.",
    }


_BUILDERS = {
    "time_series": _time_series,
    "top_n_breakdown": _top_n_breakdown,
    "distribution": _distribution,
}


def compute_chart(df: pd.DataFrame, spec: dict, mapping: dict) -> dict:
    """Compute one chart. Raises on failure; the caller drops that chart and
    continues (partial pack)."""
    chart_type = spec.get("type")
    builder = _BUILDERS.get(chart_type)
    if builder is None:
        raise ValueError(f"Unknown chart type: {chart_type!r}")
    return builder(df, spec, mapping)
