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
