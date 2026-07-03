# Capability: Aggregated Data Table View

**Phase 2.** Deferred — Phase-1 charts have no "Show data" drawer yet.

## What It Does
Shows the exact aggregated data table behind any chart (the bucket-level numbers the figure was drawn from), so the user can verify and copy the figures.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id, chart id | str | UI (`GET /api/datasets/{id}/charts/{cid}/table`) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| aggregated rows (bucket, value) | JSON | expandable table drawer in UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| pandas | re-serialize the chart's aggregated frame (bucket-level only) | 404 if chart/dataset expired |

## Business Rules
- Returns only **aggregated** bucket-level rows (never raw transactions).
- Numbers exactly match the rendered chart.

## Success Criteria
- [ ] The table values equal the corresponding chart series exactly.
- [ ] No raw transaction row is ever returned — only aggregates.
