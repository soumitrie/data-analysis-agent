"""Deterministic figure computation.

Every displayed number is computed here, by pandas, over the FULL DataFrame —
never sampled, never produced by the LLM. Each chart returns a complete Plotly
figure (data + layout) with the IB house style already applied server-side, PLUS
the exact aggregated table it plotted (bucket-level rows + column header labels).
The figure and the table are built from the SAME aggregated arrays, so they can
never disagree; the `/charts/{cid}/table` endpoint serves that table.

The LLM only chooses *which* chart types and their parameters; this module owns
all math. Parameters (bucket / grouping / sign filter / metric / top-N) let a
plain-English request map onto the same three chart families.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from analysis import housestyle
from analysis.tables import make_table

WHITELIST = {"time_series", "top_n_breakdown", "distribution"}
DEFAULT_TOP_N = 10
DEFAULT_GROUP_K = 5

_BUCKET_FREQ = {"day": "D", "week": "W-MON", "month": "ME"}
_BUCKET_LABEL = {"D": "Daily", "W-MON": "Weekly", "ME": "Monthly"}
_METRIC_LABEL = {"sum": "Total amount", "count": "Transaction count", "mean": "Mean amount"}
_SIGN_LABEL = {"inflow": "inflows only", "outflow": "outflows only", "all": "all flows"}


# ---------- helpers ----------

def _amount_series(df: pd.DataFrame, amount_col: str) -> pd.Series:
    return pd.to_numeric(df[amount_col], errors="coerce")


def _sign(spec: dict) -> str:
    s = str(spec.get("sign") or "all").lower()
    return s if s in ("inflow", "outflow", "all") else "all"


def _apply_sign(work: pd.DataFrame, sign: str) -> pd.DataFrame:
    if sign == "inflow":
        return work[work["amount"] > 0]
    if sign == "outflow":
        return work[work["amount"] < 0]
    return work


def _bucket_freq_from_spec(spec: dict, span_days: int) -> tuple[str, str]:
    """Resolve the pandas resample freq + label. Explicit `bucket` wins; else auto
    from the date span."""
    bucket = str(spec.get("bucket") or "").lower()
    if bucket in _BUCKET_FREQ:
        freq = _BUCKET_FREQ[bucket]
        return freq, _BUCKET_LABEL[freq]
    if span_days <= 31:
        return "D", "Daily"
    if span_days <= 180:
        return "W-MON", "Weekly"
    return "ME", "Monthly"


def _metric(spec: dict) -> str:
    m = str(spec.get("metric") or "sum").lower()
    return m if m in ("sum", "count", "mean") else "sum"


def _n_bins(n: int) -> int:
    if n <= 1:
        return 1
    return int(min(80, max(20, round(math.sqrt(n)))))


# ---------- chart types ----------

def _time_series(df: pd.DataFrame, spec: dict, mapping: dict) -> dict:
    date_col = mapping.get("date")
    amount_col = mapping.get("amount")
    if not date_col or not amount_col:
        raise ValueError("time_series requires both a date and an amount column")

    group_role = spec.get("group_role")
    group_col = mapping.get(group_role) if group_role in ("category", "counterparty") else None

    cols = {
        "date": pd.to_datetime(df[date_col], errors="coerce", format="mixed"),
        "amount": _amount_series(df, amount_col),
    }
    if group_col:
        cols["group"] = df[group_col].astype("string")
    work = pd.DataFrame(cols).dropna(subset=["date"])
    sign = _sign(spec)
    work = _apply_sign(work, sign)
    if work.empty:
        raise ValueError("no rows for time_series after filtering")

    span_days = int((work["date"].max() - work["date"].min()).days)
    freq, label = _bucket_freq_from_spec(spec, span_days)
    sign_note = "" if sign == "all" else f" · {_SIGN_LABEL[sign]}"

    if group_col:
        work = work.dropna(subset=["group"])
        top_k = max(1, int(spec.get("top_k") or DEFAULT_GROUP_K))
        totals = work.groupby("group")["amount"].sum()
        top_groups = list(totals.reindex(totals.abs().sort_values(ascending=False).index).head(top_k).index)
        wf = work[work["group"].isin(top_groups)]
        pivot = (
            wf.groupby([pd.Grouper(key="date", freq=freq), "group"])["amount"]
            .sum()
            .unstack(fill_value=0.0)
        )
        pivot = pivot.reindex(columns=[g for g in top_groups if g in pivot.columns])
        x = [ts.date().isoformat() for ts in pivot.index]

        fig = go.Figure()
        for i, g in enumerate(pivot.columns):
            color = housestyle.COLORWAY[i % len(housestyle.COLORWAY)]
            fig.add_trace(
                go.Scatter(
                    x=x, y=[float(v) for v in pivot[g].values], mode="lines+markers",
                    name=str(g),
                    line=dict(color=color, width=2.3),
                    marker=dict(color=color, size=5),
                    hovertemplate=f"{g}<br>%{{x}}<br>%{{y:,.2f}}<extra></extra>",
                )
            )
        title = spec.get("title") or f"{label} Total by {group_col.title()}"
        subtitle = spec.get("subtitle") or f"{label} · top {len(pivot.columns)} {group_col}{sign_note}"
        housestyle.apply_house_style(
            fig, title=title, subtitle=subtitle,
            x_title="Period", y_title="Total value", value_axis="y",
        )
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.28))

        columns = ["Period"] + [str(g) for g in pivot.columns]
        rows = [[x[r]] + [float(pivot.iloc[r, c]) for c in range(pivot.shape[1])]
                for r in range(pivot.shape[0])]
        total = float(pivot.to_numpy().sum())
        return {
            "type": "time_series",
            "title": title,
            "subtitle": subtitle,
            "figure": fig.to_plotly_json(),
            "computed_summary": {
                "total": total,
                "n_buckets": int(pivot.shape[0]),
                "freq": freq,
                "group_by": group_col,
                "series": [str(g) for g in pivot.columns],
                "sign": sign,
                "metric": "sum",
            },
            "table": make_table(columns, rows),
            "rationale": spec.get("rationale")
            or f"{label} value split across the top {len(pivot.columns)} {group_col}.",
        }

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
    title = spec.get("title") or "Total Transaction Value Over Time"
    subtitle = spec.get("subtitle") or f"{label} · sum of amount{sign_note}"
    housestyle.apply_house_style(
        fig, title=title, subtitle=subtitle,
        x_title="Period", y_title="Total value", value_axis="y",
    )
    return {
        "type": "time_series",
        "title": title,
        "subtitle": subtitle,
        "figure": fig.to_plotly_json(),
        "computed_summary": {
            "total": total,
            "n_buckets": int(len(series)),
            "freq": freq,
            "group_by": None,
            "sign": sign,
            "metric": "sum",
        },
        "table": make_table(["Period", "Total amount"], [[x[i], y[i]] for i in range(len(x))]),
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

    top_n = max(1, int(spec.get("top_n") or DEFAULT_TOP_N))
    metric = _metric(spec)
    sign = _sign(spec)
    work = pd.DataFrame({
        "group": df[group_col].astype("string"),
        "amount": _amount_series(df, amount_col),
    }).dropna(subset=["group"])
    work = _apply_sign(work, sign)
    if work.empty:
        raise ValueError("no rows for top_n_breakdown after filtering")

    agg = work.groupby("group")["amount"].agg(metric)
    if agg.empty:
        raise ValueError("no groups to aggregate for top_n_breakdown")

    ranked = agg.reindex(agg.abs().sort_values(ascending=False).index)
    top = ranked.head(top_n)
    denom = float(agg.abs().sum())
    covered_share = float(top.abs().sum() / denom) if denom else 0.0
    metric_label = _METRIC_LABEL[metric]
    sign_note = "" if sign == "all" else f" · {_SIGN_LABEL[sign]}"

    # Horizontal bars, largest at top (reverse for Plotly bottom-up ordering)
    labels = [str(i) for i in top.index][::-1]
    values = [float(v) for v in top.values][::-1]

    fig = go.Figure(
        go.Bar(
            x=values, y=labels, orientation="h",
            marker=dict(color=housestyle.NAVY),
            hovertemplate="%{y}<br>%{x:,.2f}<extra></extra>",
        )
    )
    title = spec.get("title") or f"Top {group_col.title()} by {metric_label}"
    subtitle = spec.get("subtitle") or f"Top {len(top)} · {metric_label.lower()}{sign_note}"
    housestyle.apply_house_style(
        fig, title=title, subtitle=subtitle,
        x_title=metric_label, y_title="", value_axis="x",
    )
    # Table in ranked (largest-first) order
    columns = [group_col.title(), metric_label]
    rows = [[str(idx), float(val)] for idx, val in zip(top.index, top.values)]
    return {
        "type": "top_n_breakdown",
        "title": title,
        "subtitle": subtitle,
        "figure": fig.to_plotly_json(),
        "computed_summary": {
            "top_n": int(len(top)),
            "covered_share": round(covered_share, 4),
            "group_by": group_col,
            "metric": metric,
            "sign": sign,
        },
        "table": make_table(columns, rows),
        "rationale": spec.get("rationale")
        or f"{metric_label} is concentrated among a few {group_col} — the top {len(top)} cover "
        f"{covered_share:.0%} of the gross.",
    }


def _distribution(df: pd.DataFrame, spec: dict, mapping: dict) -> dict:
    amount_col = mapping.get("amount")
    if not amount_col:
        raise ValueError("distribution requires an amount column")

    sign = _sign(spec)
    work = pd.DataFrame({"amount": _amount_series(df, amount_col)}).dropna(subset=["amount"])
    work = _apply_sign(work, sign)
    amounts = work["amount"]
    if amounts.empty:
        raise ValueError("no numeric amounts for distribution")

    nbins = int(spec.get("n_bins") or _n_bins(len(amounts)))
    counts, edges = np.histogram(amounts.to_numpy(), bins=nbins)
    centers = [float((edges[i] + edges[i + 1]) / 2) for i in range(len(counts))]
    width = float(edges[1] - edges[0]) if len(edges) > 1 else 1.0
    sign_note = "" if sign == "all" else f" · {_SIGN_LABEL[sign]}"

    fig = go.Figure(
        go.Bar(
            x=centers, y=[int(c) for c in counts],
            width=width * 0.95,
            marker=dict(color=housestyle.ACCENT),
            hovertemplate="~%{x:,.2f}<br>%{y:,} txns<extra></extra>",
        )
    )
    title = spec.get("title") or "Distribution of Transaction Sizes"
    subtitle = spec.get("subtitle") or f"Histogram · {nbins} bins{sign_note}"
    housestyle.apply_house_style(
        fig, title=title, subtitle=subtitle,
        x_title="Transaction amount", y_title="Number of transactions", value_axis="y",
    )
    columns = ["Bin center (amount)", "Transactions"]
    rows = [[centers[i], int(counts[i])] for i in range(len(counts))]
    return {
        "type": "distribution",
        "title": title,
        "subtitle": subtitle,
        "figure": fig.to_plotly_json(),
        "computed_summary": {
            "n_bins": nbins,
            "total_count": int(len(amounts)),
            "sign": sign,
        },
        "table": make_table(columns, rows),
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
    continues (partial pack). The returned dict includes both the Plotly `figure`
    and the exact aggregated `table` it plotted."""
    chart_type = spec.get("type")
    builder = _BUILDERS.get(chart_type)
    if builder is None:
        raise ValueError(f"Unknown chart type: {chart_type!r}")
    return builder(df, spec, mapping)
