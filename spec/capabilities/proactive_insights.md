# Capability: Proactive Insights & Follow-ups

**Phase 4.** Deferred.

## What It Does
Proactively flags anomalies/outliers (local detection), surfaces "so what" insights, and suggests 2–3 sharp follow-up charts the user can one-click generate.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataframe + profile + computed summaries | JSON/in-memory | prior nodes | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| anomaly flags | JSON | insights banner |
| 2–3 follow-up suggestions (each a ready chart spec) | JSON | follow-up chips |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| pandas | local anomaly/outlier detection (IQR/z-score, spikes) over full data | log; skip |
| Google Gemini | `suggest_followups` phrasing from aggregates + detected anomalies | omit suggestions, log |

## Business Rules
- Anomalies are detected **locally**; Gemini only phrases the insight/follow-up from aggregates.
- A follow-up chip maps to a concrete, validated chart spec that reuses the local compute path.

## Success Criteria
- [ ] A seeded outlier in the sample is flagged.
- [ ] Clicking a follow-up chip generates that chart with pandas-verified figures.
