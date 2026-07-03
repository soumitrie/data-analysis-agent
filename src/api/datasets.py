"""Dataset upload + analyze endpoints.

- POST /api/datasets                     — parse a CSV into an in-memory DataFrame
- POST /api/datasets/{dataset_id}/analyze — run the agent, return the chart pack
"""
from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, UploadFile, File
from pandas.api import types as pdt

from api._common import ok, api_error
from analysis.store import get_store, RowCapExceeded, MAX_ROWS
from domain.analysis import AnalyzeResult, UploadResult
from graph.runner import run_agent
from observability.events import get_logger

router = APIRouter(prefix="/api")
log = get_logger("api.datasets")

_MAX_SAMPLES = 3

_ERROR_STATUS = {
    "dataset_not_found": 404,
    "no_chartable_columns": 422,
    "planning_failed": 502,
    "internal": 500,
}


def _dtype_label(series: pd.Series) -> str:
    if pdt.is_numeric_dtype(series):
        return str(series.dtype)
    if pdt.is_datetime64_any_dtype(series):
        return "datetime"
    return "string"


def _sample_values(series: pd.Series) -> list[str]:
    vals = series.dropna().head(_MAX_SAMPLES).tolist()
    return [str(v) for v in vals]


@router.post("/datasets")
async def upload_dataset(file: UploadFile = File(...)) -> dict:
    filename = file.filename or "upload.csv"
    raw = await file.read()
    if not raw or not raw.strip():
        raise api_error("EMPTY_FILE", "The uploaded file is empty.", 400)

    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise api_error("UNPARSEABLE_CSV", f"Could not parse the file as CSV: {exc}", 400)

    if df.shape[1] == 0 or len(df) == 0:
        raise api_error("EMPTY_CSV", "The CSV has no data rows.", 400)

    try:
        entry = get_store().add(filename, df)
    except RowCapExceeded:
        raise api_error(
            "ROW_CAP_EXCEEDED",
            f"The file exceeds the maximum of {MAX_ROWS:,} rows.",
            400,
        )

    columns = [
        {
            "name": str(name),
            "dtype": _dtype_label(df[name]),
            "sample_values": _sample_values(df[name]),
        }
        for name in df.columns
    ]
    payload = UploadResult(
        dataset_id=entry.dataset_id,
        filename=filename,
        row_count=int(len(df)),
        column_count=int(df.shape[1]),
        columns=columns,
    )
    log.info(
        "upload",
        dataset_id=entry.dataset_id,
        filename=filename,
        row_count=int(len(df)),
        column_count=int(df.shape[1]),
    )
    return ok(payload.model_dump())


@router.post("/datasets/{dataset_id}/analyze")
def analyze_dataset(dataset_id: str) -> dict:
    if get_store().get(dataset_id) is None:
        raise api_error(
            "DATASET_NOT_FOUND",
            "Dataset is not in memory (expired or evicted). Please re-upload.",
            404,
        )

    result = run_agent(dataset_id)

    if result.get("status") != "completed":
        code = result.get("error_code", "internal")
        status = _ERROR_STATUS.get(code, 500)
        raise api_error(code.upper(), result.get("error", "Analysis failed."), status)

    payload = AnalyzeResult(**result)
    log.info(
        "analyze",
        dataset_id=dataset_id,
        run_id=result["run_id"],
        charts=len(result.get("charts", [])),
        status=result["status"],
        elapsed_ms=result.get("elapsed_ms"),
    )
    return ok(payload.model_dump())
