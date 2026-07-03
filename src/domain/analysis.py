"""Pydantic domain models for the charting pipeline.

These describe the API contract shapes (spec/api.md) and the LLM-bound profile
(spec/data.md). Nodes work in plain dicts internally; the API constructs these
models to validate the outgoing response shape.
"""
from __future__ import annotations

from pydantic import BaseModel


class ColumnMapping(BaseModel):
    date: str | None = None
    amount: str | None = None
    category: str | None = None
    counterparty: str | None = None
    assumption_note: str


class ProfileColumn(BaseModel):
    name: str
    dtype: str
    cardinality: int
    role: str | None = None


class DateRange(BaseModel):
    start: str | None = None
    end: str | None = None


class AmountSummary(BaseModel):
    sum: float
    mean: float
    min: float
    max: float
    q1: float
    median: float
    q3: float


class TopCategory(BaseModel):
    label: str
    total: float
    count: int


class LLMProfile(BaseModel):
    row_count: int
    columns: list[ProfileColumn]
    date_range: DateRange
    amount_summary: AmountSummary | None = None
    top_categories: list[TopCategory] = []


class Chart(BaseModel):
    id: str
    type: str
    title: str
    subtitle: str
    figure: dict
    computed_summary: dict
    rationale: str


class Usage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated_cost_usd: float | None = None


class AnalyzeResult(BaseModel):
    run_id: str
    dataset_id: str
    status: str
    column_mapping: ColumnMapping
    profile: LLMProfile
    charts: list[Chart]
    usage: Usage
    elapsed_ms: int


class ColumnPreview(BaseModel):
    name: str
    dtype: str
    sample_values: list[str]


class UploadResult(BaseModel):
    dataset_id: str
    filename: str
    row_count: int
    column_count: int
    columns: list[ColumnPreview]
