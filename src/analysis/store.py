"""In-memory, process-local store of uploaded datasets.

Raw transaction rows live ONLY here, in process memory — never written to disk,
never sent to the LLM. LRU-capped to a few datasets; per-dataset row cap of 1M.
A single uvicorn worker (reload=False) keeps this authoritative for the session.
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd

MAX_DATASETS = 4
MAX_ROWS = 1_000_000


class RowCapExceeded(ValueError):
    """Raised when an uploaded dataset exceeds the per-dataset row cap."""


@dataclass
class DatasetEntry:
    dataset_id: str
    filename: str
    dataframe: pd.DataFrame
    created_at: datetime
    messages: list = field(default_factory=list)  # populated from Phase 2
    charts: list = field(default_factory=list)     # populated from Phase 2


class DatasetStore:
    def __init__(self, max_datasets: int = MAX_DATASETS, max_rows: int = MAX_ROWS) -> None:
        self._data: "OrderedDict[str, DatasetEntry]" = OrderedDict()
        self._lock = threading.Lock()
        self._max_datasets = max_datasets
        self._max_rows = max_rows

    def add(self, filename: str, dataframe: pd.DataFrame) -> DatasetEntry:
        if len(dataframe) > self._max_rows:
            raise RowCapExceeded(
                f"Dataset has {len(dataframe)} rows, exceeding the cap of {self._max_rows}."
            )
        entry = DatasetEntry(
            dataset_id=str(uuid4()),
            filename=filename,
            dataframe=dataframe,
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._data[entry.dataset_id] = entry
            self._data.move_to_end(entry.dataset_id)
            while len(self._data) > self._max_datasets:
                self._data.popitem(last=False)  # evict oldest (LRU)
        return entry

    def get(self, dataset_id: str) -> DatasetEntry | None:
        with self._lock:
            entry = self._data.get(dataset_id)
            if entry is not None:
                self._data.move_to_end(dataset_id)  # mark most-recently-used
            return entry

    # ---- Phase 2: per-session chart registry + conversation memory ----

    def set_auto_charts(self, dataset_id: str, charts: list[dict]) -> None:
        """Replace the session chart registry with a fresh auto-pack (each chart
        dict carries its `id` and aggregated `table`). Called after analyze so the
        `/table` drawer works for auto-pack charts. Re-analyze starts a clean pack."""
        with self._lock:
            entry = self._data.get(dataset_id)
            if entry is None:
                return
            entry.charts = list(charts)

    def append_chart(self, dataset_id: str, chart: dict) -> None:
        """Append one asked chart (with its `id` + `table`) to the session registry."""
        with self._lock:
            entry = self._data.get(dataset_id)
            if entry is None:
                return
            entry.charts.append(chart)

    def get_chart(self, dataset_id: str, chart_id: str) -> dict | None:
        with self._lock:
            entry = self._data.get(dataset_id)
            if entry is None:
                return None
            for chart in entry.charts:
                if chart.get("id") == chart_id:
                    return chart
            return None

    def count_asked_charts(self, dataset_id: str) -> int:
        with self._lock:
            entry = self._data.get(dataset_id)
            if entry is None:
                return 0
            return sum(1 for c in entry.charts if str(c.get("id", "")).startswith("q"))

    def append_message(self, dataset_id: str, message: dict) -> None:
        """Append a compact conversation record (request text + a short summary of
        the resulting chart). NEVER contains raw transaction rows."""
        with self._lock:
            entry = self._data.get(dataset_id)
            if entry is None:
                return
            entry.messages.append(message)

    def get_messages(self, dataset_id: str) -> list[dict]:
        with self._lock:
            entry = self._data.get(dataset_id)
            if entry is None:
                return []
            return list(entry.messages)

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def __contains__(self, dataset_id: str) -> bool:
        with self._lock:
            return dataset_id in self._data


_store: DatasetStore | None = None


def get_store() -> DatasetStore:
    global _store
    if _store is None:
        _store = DatasetStore()
    return _store
