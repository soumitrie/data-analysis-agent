"""DatasetStore — LRU eviction, row cap, and Phase-2 session memory.

No LLM key required. The session-memory surface (append_chart / count_asked_charts
/ append_message / get_messages) is what gives NL follow-ups their context and
what accumulates asked charts across a session — proven directly here.
"""
import json

import pandas as pd
import pytest

from analysis.store import DatasetStore, RowCapExceeded


def _df(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame({"a": range(n)})


def test_add_and_get_roundtrip():
    store = DatasetStore()
    entry = store.add("f.csv", _df())
    fetched = store.get(entry.dataset_id)
    assert fetched is not None
    assert fetched.filename == "f.csv"
    assert len(fetched.dataframe) == 3


def test_get_missing_returns_none():
    store = DatasetStore()
    assert store.get("nope") is None


def test_lru_evicts_oldest_beyond_cap():
    store = DatasetStore(max_datasets=2)
    a = store.add("a.csv", _df())
    b = store.add("b.csv", _df())
    c = store.add("c.csv", _df())  # should evict a
    assert store.get(a.dataset_id) is None
    assert store.get(b.dataset_id) is not None
    assert store.get(c.dataset_id) is not None
    assert len(store) == 2


def test_get_marks_recently_used():
    store = DatasetStore(max_datasets=2)
    a = store.add("a.csv", _df())
    b = store.add("b.csv", _df())
    store.get(a.dataset_id)          # a is now most-recently-used
    c = store.add("c.csv", _df())    # should evict b, not a
    assert store.get(a.dataset_id) is not None
    assert store.get(b.dataset_id) is None
    assert store.get(c.dataset_id) is not None


def test_row_cap_rejected():
    store = DatasetStore(max_rows=5)
    with pytest.raises(RowCapExceeded):
        store.add("big.csv", _df(6))


# --------------------------------------------------------------------------- #
#  Phase-2 session memory: chart accumulation + conversation records
# --------------------------------------------------------------------------- #

def test_append_chart_and_count_asked_charts():
    """count_asked_charts counts ONLY q-prefixed (asked) charts — the auto-pack
    c-charts never inflate the next asked chart's id."""
    store = DatasetStore()
    did = store.add("f.csv", _df()).dataset_id

    assert store.count_asked_charts(did) == 0
    store.set_auto_charts(did, [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}])
    assert store.count_asked_charts(did) == 0  # auto-pack does not count

    store.append_chart(did, {"id": "q1", "table": {"columns": [], "rows": []}})
    assert store.count_asked_charts(did) == 1
    store.append_chart(did, {"id": "q2", "table": {"columns": [], "rows": []}})
    assert store.count_asked_charts(did) == 2

    # get_chart resolves both auto-pack and asked charts by id
    assert store.get_chart(did, "c1")["id"] == "c1"
    assert store.get_chart(did, "q2")["id"] == "q2"
    assert store.get_chart(did, "nope") is None


def test_append_and_get_messages_roundtrip_returns_copy():
    store = DatasetStore()
    did = store.add("f.csv", _df()).dataset_id

    assert store.get_messages(did) == []
    store.append_message(did, {"request_text": "monthly total", "chart_title": "Monthly Total"})
    store.append_message(did, {"request_text": "top payees", "chart_title": "Top Payees"})

    msgs = store.get_messages(did)
    assert [m["request_text"] for m in msgs] == ["monthly total", "top payees"]

    # get_messages returns a copy — mutating it must not corrupt session memory
    msgs.append({"request_text": "injected"})
    assert len(store.get_messages(did)) == 2


def test_stored_messages_carry_no_raw_rows():
    """Session memory holds only request_text + a compact chart summary — never a
    raw transaction row. This is the privacy invariant for conversation memory."""
    store = DatasetStore()
    df = pd.DataFrame({
        "txn_id": ["TXN-0001", "TXN-0002"],
        "amount": [12345.67, -8901.23],
        "counterparty": ["ACME Holdings", "Globex Ltd"],
    })
    did = store.add("ledger.csv", df).dataset_id

    # Mirror exactly the compact record the runner appends after an ask.
    store.append_message(did, {
        "request_text": "monthly total by category",
        "chart_id": "q1",
        "chart_title": "Monthly Total by Category",
        "chart_type": "time_series",
        "declined": False,
    })

    flat = json.dumps(store.get_messages(did))
    for raw in ("TXN-0001", "TXN-0002", "12345.67", "-8901.23", "ACME Holdings", "Globex Ltd"):
        assert raw not in flat, f"raw datum {raw!r} leaked into session memory"

    msg = store.get_messages(did)[0]
    assert set(msg) <= {"request_text", "chart_id", "chart_title", "chart_type", "declined"}


def test_session_memory_ops_on_missing_dataset_are_safe_noops():
    store = DatasetStore()
    store.append_chart("nope", {"id": "q1"})
    store.append_message("nope", {"request_text": "x"})
    assert store.count_asked_charts("nope") == 0
    assert store.get_messages("nope") == []
    assert store.get_chart("nope", "q1") is None
