"""Deterministic figure computation + house style. No LLM key required."""
import pytest

from analysis import figures, housestyle


MAPPING = {
    "date": "txn_date",
    "amount": "amount",
    "category": "category",
    "counterparty": "counterparty",
    "assumption_note": "note",
}


def _assert_house_style(fig: dict):
    layout = fig["layout"]
    assert layout["font"]["family"] == housestyle.FONT_FAMILY
    assert housestyle.NAVY in layout["colorway"]
    assert housestyle.ACCENT in layout["colorway"]
    assert layout["margin"]["l"] == housestyle.MARGIN["l"]
    assert layout["paper_bgcolor"] == "#FFFFFF"
    # provenance footnote present
    texts = [a.get("text") for a in layout.get("annotations", [])]
    assert housestyle.FOOTNOTE in texts


def test_time_series_total_equals_full_sum(sample_df):
    chart = figures.compute_chart(sample_df, {"type": "time_series"}, MAPPING)
    assert chart["type"] == "time_series"
    assert chart["computed_summary"]["total"] == pytest.approx(
        float(sample_df["amount"].sum()), rel=1e-9
    )
    assert chart["computed_summary"]["n_buckets"] > 0
    assert chart["figure"]["data"] and chart["figure"]["layout"]
    _assert_house_style(chart["figure"])


def test_distribution_total_count_equals_len(sample_df):
    chart = figures.compute_chart(sample_df, {"type": "distribution"}, MAPPING)
    assert chart["computed_summary"]["total_count"] == len(sample_df)
    assert 20 <= chart["computed_summary"]["n_bins"] <= 80
    _assert_house_style(chart["figure"])


def test_top_n_breakdown_covered_share_bounded(sample_df):
    chart = figures.compute_chart(sample_df, {"type": "top_n_breakdown"}, MAPPING)
    cs = chart["computed_summary"]
    assert cs["top_n"] == 10
    assert 0.0 <= cs["covered_share"] <= 1.0
    assert cs["group_by"] == "counterparty"
    _assert_house_style(chart["figure"])


def test_unknown_chart_type_raises(sample_df):
    with pytest.raises(ValueError):
        figures.compute_chart(sample_df, {"type": "pie_of_pies"}, MAPPING)


def test_time_series_requires_date():
    import pandas as pd
    df = pd.DataFrame({"amount": [1.0, 2.0, 3.0]})
    mapping = {"date": None, "amount": "amount"}
    with pytest.raises(ValueError):
        figures.compute_chart(df, {"type": "time_series"}, mapping)
