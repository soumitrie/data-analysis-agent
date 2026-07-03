# Capability: Full Chart Arsenal

**Phase 3.** Deferred — Phase 1/2 render only the 3 core chart types.

## What It Does
Extends the whitelist and figure engine to the full arsenal: composition (stacked/waterfall/treemap), flow (Sankey), concentration (heatmap), and box/outlier charts — selectable by the auto-pack and NL requests.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| chart spec (extended types) | JSON | plan_charts / plan_from_nl | yes |
| dataframe | in-memory | DatasetStore | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| Plotly figures for new chart types (house-styled) | JSON | chart pack |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| pandas | compute the extended aggregations (flow matrices, quantiles, pivots) | per-chart error → drop chart, log |
| Google Gemini | selects from the expanded whitelist (aggregates only) | fallback plan |

## Business Rules
- Every new chart type carries the IB house style and computes figures locally over full data.
- Sankey/flow uses aggregated counterparty→category (or period→period) totals only.

## Success Criteria
- [ ] Each new chart type renders with correct, pandas-verified aggregated figures.
- [ ] The house style is consistent across all arsenal types.
