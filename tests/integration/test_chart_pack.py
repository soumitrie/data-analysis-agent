"""End-to-end chart pack — real Gemini via AGENT_GEMINI_API_KEY, SQLite driver.

Skips ONLY if no LLM key is genuinely present; the key is set in .env, so this
must run and pass.
"""
import json

import pytest

pytestmark = pytest.mark.usefixtures("_require_llm_key")


def _upload_and_analyze(api_client, sample_csv_path):
    with open(sample_csv_path, "rb") as fh:
        up = api_client.post(
            "/api/datasets",
            files={"file": ("transactions_sample.csv", fh, "text/csv")},
        )
    assert up.status_code == 200, up.text
    up_data = up.json()["data"]
    dataset_id = up_data["dataset_id"]

    an = api_client.post(f"/api/datasets/{dataset_id}/analyze")
    assert an.status_code == 200, an.text
    return up_data, an.json()["data"]


def test_upload_returns_counts_and_previews(api_client, sample_csv_path):
    with open(sample_csv_path, "rb") as fh:
        r = api_client.post(
            "/api/datasets",
            files={"file": ("transactions_sample.csv", fh, "text/csv")},
        )
    data = r.json()["data"]
    assert data["row_count"] > 5000
    assert data["column_count"] == 6
    names = {c["name"] for c in data["columns"]}
    assert {"txn_date", "amount", "category", "counterparty"} <= names
    for c in data["columns"]:
        assert len(c["sample_values"]) <= 3


def test_analyze_produces_three_chart_pack(api_client, sample_csv_path, sample_df):
    _, result = _upload_and_analyze(api_client, sample_csv_path)

    assert result["status"] == "completed"
    assert len(result["charts"]) == 3

    # mapping: all four roles + non-empty assumption note
    m = result["column_mapping"]
    assert m["date"] == "txn_date"
    assert m["amount"] == "amount"
    assert m["category"] == "category"
    assert m["counterparty"] == "counterparty"
    assert m["assumption_note"].strip()

    charts = {c["type"]: c for c in result["charts"]}
    assert set(charts) == {"time_series", "top_n_breakdown", "distribution"}

    # trend total == FULL df sum (proves full-data, not sampled, computation)
    full_sum = float(sample_df["amount"].sum())
    assert charts["time_series"]["computed_summary"]["total"] == pytest.approx(full_sum, rel=1e-6)

    # histogram total_count == len(df)
    assert charts["distribution"]["computed_summary"]["total_count"] == len(sample_df)

    # every figure is a valid Plotly figure with the house style applied
    from analysis import housestyle
    for chart in result["charts"]:
        fig = chart["figure"]
        assert fig["data"] and fig["layout"]
        assert fig["layout"]["font"]["family"] == housestyle.FONT_FAMILY
        assert housestyle.NAVY in fig["layout"]["colorway"]

    # usage captured from the real Gemini call
    assert result["usage"]["prompt_tokens"] is not None
    assert result["usage"]["completion_tokens"] is not None


def test_gemini_prompt_contains_no_raw_row(api_client, sample_csv_path, sample_df):
    """The serialized Gemini prompt must contain NO raw transaction row."""
    from graph.nodes import build_plan_messages
    from analysis import profiling, columns as col_detect

    prof = profiling.build_profile(sample_df)
    mapping = col_detect.detect_roles(sample_df, prof)
    system, user = build_plan_messages(prof, mapping, None)
    payload = system + "\n" + user

    # no raw txn_id VALUE may appear (the column *name* is fine, values are not)
    for txn_id in sample_df["txn_id"].dropna().head(50):
        assert str(txn_id) not in payload

    # no full-row fingerprint: a raw amount paired with its counterparty in one row
    row = sample_df.iloc[0]
    assert not (str(row["amount"]) in user and str(row["txn_id"]) in user)

    # the payload IS valid JSON of aggregates only
    parsed = json.loads(user)
    assert "profile" in parsed
    assert parsed["profile"]["row_count"] == len(sample_df)


def test_analyze_missing_dataset_returns_404(api_client):
    r = api_client.post("/api/datasets/does-not-exist/analyze")
    assert r.status_code == 404
    body = r.json()
    assert body["data"] is None
    assert body["error"]["code"]


def test_upload_empty_file_rejected(api_client):
    r = api_client.post(
        "/api/datasets",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"]
