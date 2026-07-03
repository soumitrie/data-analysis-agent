"""Aggregated profiling. No LLM key required."""
import pandas as pd
import pytest

from analysis import profiling


def test_profile_aggregates_match_pandas(sample_df):
    prof = profiling.build_profile(sample_df)
    assert prof["row_count"] == len(sample_df)

    amt = prof["amount_summary"]
    assert amt is not None
    assert amt["sum"] == pytest.approx(float(sample_df["amount"].sum()), rel=1e-9)
    assert amt["min"] == pytest.approx(float(sample_df["amount"].min()), rel=1e-9)
    assert amt["max"] == pytest.approx(float(sample_df["amount"].max()), rel=1e-9)


def test_profile_date_range(sample_df):
    prof = profiling.build_profile(sample_df)
    assert prof["date_range"]["start"] == "2024-01-01"
    assert prof["date_range"]["end"].startswith("2024-12")


def test_profile_top_categories_present(sample_df):
    prof = profiling.build_profile(sample_df)
    labels = {c["label"] for c in prof["top_categories"]}
    assert "Wire Out" in labels
    for c in prof["top_categories"]:
        assert c["count"] > 0


def test_profile_has_no_raw_txn_id_values(sample_df):
    """The profile must not carry raw transaction identifiers — only aggregates."""
    prof = profiling.build_profile(sample_df)
    import json
    blob = json.dumps(prof, default=str)
    sample_txn = str(sample_df["txn_id"].iloc[0])
    assert sample_txn not in blob


def test_apply_roles_annotates_columns(sample_df):
    prof = profiling.build_profile(sample_df)
    mapping = {"date": "txn_date", "amount": "amount", "category": "category", "counterparty": "counterparty"}
    profiling.apply_roles(prof, mapping)
    role_by_name = {c["name"]: c["role"] for c in prof["columns"]}
    assert role_by_name["txn_date"] == "date"
    assert role_by_name["amount"] == "amount"
    assert role_by_name["txn_id"] is None
