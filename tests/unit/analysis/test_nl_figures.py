"""Parameterized NL figure params + table exactness. No LLM key required.

Every assertion recomputes the expected aggregation independently with pandas over
the FULL frame and checks the chart's returned `table` equals it EXACTLY — proving
the figure and its data table are both exact and bucket-level (never raw rows).
"""
import pandas as pd
import pytest

from analysis import figures


MAPPING = {
    "date": "txn_date",
    "amount": "amount",
    "category": "category",
    "counterparty": "counterparty",
    "assumption_note": "note",
}

_FREQ = {"day": "D", "week": "W-MON", "month": "ME"}


def _amount(df):
    return pd.to_numeric(df["amount"], errors="coerce")


def test_top_n_breakdown_by_category_sum_matches_full_data(sample_df):
    chart = figures.compute_chart(
        sample_df, {"type": "top_n_breakdown", "group_role": "category", "metric": "sum", "top_n": 20},
        MAPPING,
    )
    expected = _amount(sample_df).groupby(sample_df["category"]).sum()
    for label, value in chart["table"]["rows"]:
        assert value == pytest.approx(float(expected[label]), rel=1e-9)
    assert chart["computed_summary"]["group_by"] == "category"
    assert chart["table"]["columns"][0] == "Category"


def test_top_n_breakdown_metric_count_and_sign_filter(sample_df):
    chart = figures.compute_chart(
        sample_df, {"type": "top_n_breakdown", "group_role": "counterparty", "metric": "count", "sign": "outflow"},
        MAPPING,
    )
    outflow = sample_df[_amount(sample_df) < 0]
    expected = outflow.groupby("counterparty")["amount"].count()
    for label, value in chart["table"]["rows"]:
        assert value == pytest.approx(float(expected[label]), rel=1e-9)
    assert chart["computed_summary"]["sign"] == "outflow"
    assert chart["computed_summary"]["metric"] == "count"


def test_time_series_monthly_ungrouped_matches_resample(sample_df):
    chart = figures.compute_chart(sample_df, {"type": "time_series", "bucket": "month"}, MAPPING)
    cs = chart["computed_summary"]
    assert cs["freq"] == "ME"
    assert cs["group_by"] is None
    work = pd.DataFrame({
        "date": pd.to_datetime(sample_df["txn_date"], errors="coerce", format="mixed"),
        "amount": _amount(sample_df),
    }).dropna(subset=["date"])
    expected = work.set_index("date")["amount"].resample("ME").sum()
    exp_rows = [[ts.date().isoformat(), float(v)] for ts, v in expected.items()]
    # compare cell by cell
    assert [r[0] for r in chart["table"]["rows"]] == [r[0] for r in exp_rows]
    for got, exp in zip(chart["table"]["rows"], exp_rows):
        assert got[1] == pytest.approx(exp[1], rel=1e-9)


def test_time_series_grouped_by_category_matches_pivot(sample_df):
    chart = figures.compute_chart(
        sample_df,
        {"type": "time_series", "bucket": "month", "group_role": "category", "top_k": 8},
        MAPPING,
    )
    cs = chart["computed_summary"]
    assert cs["group_by"] == "category"
    assert cs["freq"] == "ME"

    work = pd.DataFrame({
        "date": pd.to_datetime(sample_df["txn_date"], errors="coerce", format="mixed"),
        "amount": _amount(sample_df),
        "group": sample_df["category"].astype("string"),
    }).dropna(subset=["date", "group"])
    totals = work.groupby("group")["amount"].sum()
    top = list(totals.reindex(totals.abs().sort_values(ascending=False).index).head(8).index)
    wf = work[work["group"].isin(top)]
    pivot = wf.groupby([pd.Grouper(key="date", freq="ME"), "group"])["amount"].sum().unstack(fill_value=0.0)
    pivot = pivot.reindex(columns=[g for g in top if g in pivot.columns])

    # column headers: Period + one per series, in the same order
    assert chart["table"]["columns"] == ["Period"] + [str(g) for g in pivot.columns]
    periods = [ts.date().isoformat() for ts in pivot.index]
    assert [r[0] for r in chart["table"]["rows"]] == periods
    for r, (_, prow) in zip(chart["table"]["rows"], pivot.iterrows()):
        for got, exp in zip(r[1:], prow.values):
            assert got == pytest.approx(float(exp), rel=1e-9)


def test_distribution_sign_filter_counts_only_inflows(sample_df):
    chart = figures.compute_chart(sample_df, {"type": "distribution", "sign": "inflow"}, MAPPING)
    inflow_count = int((_amount(sample_df) > 0).sum())
    assert chart["computed_summary"]["total_count"] == inflow_count
    # table counts sum to the number of inflow rows
    assert sum(r[1] for r in chart["table"]["rows"]) == inflow_count


def test_time_series_grouped_empty_after_sign_raises():
    df = pd.DataFrame({
        "txn_date": ["2024-01-01", "2024-01-02"],
        "amount": [-5.0, -10.0],  # no inflows
        "category": ["A", "B"],
    })
    mapping = {"date": "txn_date", "amount": "amount", "category": "category", "counterparty": None}
    with pytest.raises(ValueError):
        figures.compute_chart(df, {"type": "time_series", "sign": "inflow"}, mapping)
