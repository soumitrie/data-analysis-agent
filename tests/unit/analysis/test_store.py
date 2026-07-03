"""DatasetStore — LRU eviction and row cap. No LLM key required."""
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
