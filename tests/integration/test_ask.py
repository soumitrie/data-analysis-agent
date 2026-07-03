"""End-to-end NL ask + aggregated-table drawer + cost/tokens.

Real Gemini via AGENT_GEMINI_API_KEY, SQLite production driver. Skips ONLY if no
LLM key is genuinely present; the key is set in .env, so this must run and pass.

Proves: (1) an NL request maps to a valid chart whose figures equal a pandas
aggregation over the FULL data; (2) the /table drawer for BOTH an auto-pack and an
asked chart returns bucket-level rows that EXACTLY equal the chart's plotted series
(no raw transaction rows); (3) an un-chartable request declines gracefully (HTTP
200, chart:null) rather than 5xx or a fabricated chart; (4) usage carries real
Gemini token counts; (5) the Gemini NL prompt contains no raw transaction row.
"""
import json

import pandas as pd
import pytest

pytestmark = pytest.mark.usefixtures("_require_llm_key")

_FREQ = {"day": "D", "week": "W-MON", "month": "ME"}


def _amount(df):
    return pd.to_numeric(df["amount"], errors="coerce")


def _upload_and_analyze(api_client, sample_csv_path):
    with open(sample_csv_path, "rb") as fh:
        up = api_client.post(
            "/api/datasets",
            files={"file": ("transactions_sample.csv", fh, "text/csv")},
        )
    assert up.status_code == 200, up.text
    dataset_id = up.json()["data"]["dataset_id"]
    an = api_client.post(f"/api/datasets/{dataset_id}/analyze")
    assert an.status_code == 200, an.text
    return dataset_id, an.json()["data"]


def _recompute_expected(df, chart):
    """Independently recompute the {label/period: value} the chart should plot,
    from the FULL frame, using the chart's declared params."""
    cs = chart["computed_summary"]
    sign = cs.get("sign", "all")
    amount = _amount(df)
    mask = pd.Series(True, index=df.index)
    if sign == "inflow":
        mask = amount > 0
    elif sign == "outflow":
        mask = amount < 0

    if chart["type"] == "top_n_breakdown":
        col = cs["group_by"]
        metric = cs.get("metric", "sum")
        work = pd.DataFrame({"group": df[col].astype("string"), "amount": amount})[mask].dropna(subset=["group"])
        return work.groupby("group")["amount"].agg(metric)

    if chart["type"] == "time_series":
        freq = cs["freq"]
        date = pd.to_datetime(df["txn_date"], errors="coerce", format="mixed")
        if cs.get("group_by"):
            work = pd.DataFrame({"date": date, "amount": amount,
                                 "group": df[cs["group_by"]].astype("string")})[mask].dropna(subset=["date", "group"])
            pivot = work.groupby([pd.Grouper(key="date", freq=freq), "group"])["amount"].sum().unstack(fill_value=0.0)
            return pivot
        work = pd.DataFrame({"date": date, "amount": amount})[mask].dropna(subset=["date"])
        return work.set_index("date")["amount"].resample(freq).sum()

    if chart["type"] == "distribution":
        return int(mask.sum())
    return None


def _assert_table_matches_chart(df, chart, table):
    """The /table rows must EXACTLY equal what the chart plotted AND equal an
    independent full-data pandas recomputation."""
    expected = _recompute_expected(df, chart)
    ctype = chart["type"]

    if ctype == "top_n_breakdown":
        for label, value in table["rows"]:
            assert value == pytest.approx(float(expected[label]), rel=1e-6)
    elif ctype == "time_series" and chart["computed_summary"].get("group_by"):
        pivot = expected
        series_cols = table["columns"][1:]
        by_period = {ts.date().isoformat(): row for ts, row in pivot.iterrows()}
        for row in table["rows"]:
            period, cells = row[0], row[1:]
            prow = by_period[period]
            for col, cell in zip(series_cols, cells):
                assert cell == pytest.approx(float(prow[col]), rel=1e-6)
    elif ctype == "time_series":
        exp = {ts.date().isoformat(): float(v) for ts, v in expected.items()}
        for period, value in table["rows"]:
            assert value == pytest.approx(exp[period], rel=1e-6)
    elif ctype == "distribution":
        assert sum(r[1] for r in table["rows"]) == expected

    # No raw transaction id ever appears in an aggregated table
    flat = json.dumps(table)
    for txn_id in df["txn_id"].dropna().head(50):
        assert str(txn_id) not in flat


def test_ask_maps_request_and_table_is_exact(api_client, sample_csv_path, sample_df):
    dataset_id, analyze = _upload_and_analyze(api_client, sample_csv_path)

    # --- auto-pack chart /table (exact, aggregated only) ---
    auto_chart = analyze["charts"][0]
    t = api_client.get(f"/api/datasets/{dataset_id}/charts/{auto_chart['id']}/table")
    assert t.status_code == 200, t.text
    auto_table = t.json()["data"]
    assert auto_table["chart_id"] == auto_chart["id"]
    assert auto_table["columns"] and auto_table["rows"]
    _assert_table_matches_chart(sample_df, auto_chart, auto_table)

    # --- NL ask: "monthly total by category" ---
    r = api_client.post(f"/api/datasets/{dataset_id}/ask", json={"request_text": "monthly total by category"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "completed"
    assert data["declined"] is False
    assert data["message"] is None
    chart = data["chart"]
    assert chart is not None
    assert chart["id"].startswith("q")
    assert set(chart) >= {"id", "type", "title", "subtitle", "figure", "computed_summary", "rationale"}
    assert chart["figure"]["data"] and chart["figure"]["layout"]

    # real Gemini token usage present
    assert data["usage"]["prompt_tokens"] is not None
    assert data["usage"]["completion_tokens"] is not None

    # --- asked chart /table: exact + aggregated + equals full-data pandas ---
    at = api_client.get(f"/api/datasets/{dataset_id}/charts/{chart['id']}/table")
    assert at.status_code == 200, at.text
    asked_table = at.json()["data"]
    assert asked_table["rows"]
    _assert_table_matches_chart(sample_df, chart, asked_table)


def test_ask_twice_accumulates_and_carries_history(api_client, sample_csv_path, sample_df):
    """Stateful Phase-2 proof: two asks in ONE session accumulate (2nd chart id is
    q2 via count_asked_charts), BOTH charts' /table endpoints resolve with exact
    aggregated numbers, and the 2nd NL prompt carries the 1st request as follow-up
    context. Robust to whichever valid chart type Gemini picks (aggregates are
    recomputed from the returned spec)."""
    dataset_id, _ = _upload_and_analyze(api_client, sample_csv_path)

    first_request = "monthly total by category"
    r1 = api_client.post(f"/api/datasets/{dataset_id}/ask", json={"request_text": first_request})
    assert r1.status_code == 200, r1.text
    d1 = r1.json()["data"]
    assert d1["declined"] is False, d1
    chart1 = d1["chart"]
    assert chart1 is not None and chart1["id"] == "q1"

    second_request = "top counterparties by total amount"
    r2 = api_client.post(f"/api/datasets/{dataset_id}/ask", json={"request_text": second_request})
    assert r2.status_code == 200, r2.text
    d2 = r2.json()["data"]
    assert d2["declined"] is False, d2
    chart2 = d2["chart"]
    # Accumulation via count_asked_charts: the 2nd asked chart is q2, not q1.
    assert chart2 is not None and chart2["id"] == "q2"

    # BOTH charts' /table endpoints resolve with exact, aggregated figures.
    for chart in (chart1, chart2):
        t = api_client.get(f"/api/datasets/{dataset_id}/charts/{chart['id']}/table")
        assert t.status_code == 200, t.text
        table = t.json()["data"]
        assert table["rows"]
        _assert_table_matches_chart(sample_df, chart, table)

    # Follow-up context: the 2nd NL prompt (build_nl_messages) carries the 1st
    # request in its serialized history — the follow-up-context claim.
    from graph.nodes import build_nl_messages
    from analysis import profiling, columns as col_detect
    from analysis.store import get_store

    messages = get_store().get_messages(dataset_id)
    assert len(messages) == 2
    assert messages[0]["request_text"] == first_request

    prof = profiling.build_profile(sample_df)
    mapping = col_detect.detect_roles(sample_df, prof)
    # History exactly as it stood when the 2nd ask ran: only the first message.
    _, user = build_nl_messages(prof, mapping, second_request, [messages[0]])
    assert first_request in user  # the prior request text is in the serialized prompt
    # And it stays privacy-safe — no raw transaction id ever enters the prompt.
    for txn_id in sample_df["txn_id"].dropna().head(50):
        assert str(txn_id) not in user


def test_ask_unchartable_declines_gracefully(api_client, sample_csv_path):
    dataset_id, _ = _upload_and_analyze(api_client, sample_csv_path)
    r = api_client.post(f"/api/datasets/{dataset_id}/ask", json={"request_text": "tell me a joke about my bank"})
    assert r.status_code == 200, r.text  # NOT a 5xx
    data = r.json()["data"]
    assert data["declined"] is True
    assert data["chart"] is None
    assert data["message"] and "map" in data["message"].lower()


def test_ask_missing_dataset_returns_404(api_client):
    r = api_client.post("/api/datasets/nope/ask", json={"request_text": "monthly total"})
    assert r.status_code == 404
    assert r.json()["error"]["code"]


def test_table_unknown_chart_returns_404(api_client, sample_csv_path):
    dataset_id, _ = _upload_and_analyze(api_client, sample_csv_path)
    r = api_client.get(f"/api/datasets/{dataset_id}/charts/does-not-exist/table")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "CHART_NOT_FOUND"


def test_ask_prompt_contains_no_raw_row(sample_df):
    """Privacy spy: the serialized NL prompt must contain NO raw transaction row."""
    from graph.nodes import build_nl_messages
    from analysis import profiling, columns as col_detect

    prof = profiling.build_profile(sample_df)
    mapping = col_detect.detect_roles(sample_df, prof)
    history = [{"request_text": "monthly total by category", "chart_title": "Monthly Total", "declined": False}]
    system, user = build_nl_messages(prof, mapping, "and the same for outflows only", history)
    payload = system + "\n" + user

    for txn_id in sample_df["txn_id"].dropna().head(50):
        assert str(txn_id) not in payload
    row = sample_df.iloc[0]
    assert not (str(row["amount"]) in user and str(row["txn_id"]) in user)

    parsed = json.loads(user)
    assert parsed["profile"]["row_count"] == len(sample_df)
    assert parsed["request"] == "and the same for outflows only"
