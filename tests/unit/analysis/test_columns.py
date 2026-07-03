"""Column-role detection on the sample. No LLM key required."""
import pandas as pd

from analysis import columns as col_detect


def test_detects_all_four_roles_on_sample(sample_df):
    mapping = col_detect.detect_roles(sample_df)
    assert mapping["date"] == "txn_date"
    assert mapping["amount"] == "amount"
    assert mapping["category"] == "category"
    assert mapping["counterparty"] == "counterparty"
    assert mapping["assumption_note"]
    assert "txn_date" in mapping["assumption_note"]


def test_id_like_column_not_chosen_as_counterparty(sample_df):
    mapping = col_detect.detect_roles(sample_df)
    # txn_id is near-unique → must not be picked as counterparty
    assert mapping["counterparty"] != "txn_id"


def test_no_amount_when_no_numeric_column():
    df = pd.DataFrame({"label": ["a", "b", "c"], "note": ["x", "y", "z"]})
    mapping = col_detect.detect_roles(df)
    assert mapping["amount"] is None


def test_name_hint_overrides_for_amount():
    df = pd.DataFrame({
        "seq": [1, 2, 3, 4],
        "amount": [-10.0, 20.5, -3.0, 99.9],
        "label": ["a", "b", "c", "d"],
    })
    mapping = col_detect.detect_roles(df)
    assert mapping["amount"] == "amount"
