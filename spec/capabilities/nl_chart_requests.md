# Capability: NL Chart Requests

**Phase 2.** Deferred — Phase-1 UI shows this as a labelled "Ask… (Phase 2)" stub.

## What It Does
Lets the user type a plain-English request over the already-loaded dataset ("daily volume for the top 3 counterparties") and adds the resulting chart to the pack, with prior requests in the session giving follow-ups context.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | str | loaded session | yes |
| request_text | str | Ask box (`POST /api/datasets/{id}/ask`) | yes |
| session history | list | DatasetStore.messages | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| new chart (Plotly figure JSON) | JSON | appended to chart pack |
| updated session history | in-memory | DatasetStore |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Google Gemini | `plan_from_nl` — map request + profile to a validated chart spec | retry once; if unmappable, return a friendly "couldn't interpret" message, no chart |
| pandas | compute the figure over full data | per-chart error → surfaced message |

## Business Rules
- Same privacy rule: only profile + prior-request summaries go to Gemini, never raw rows.
- The request is mapped to the chart whitelist; out-of-scope requests get a helpful decline, not a hallucinated chart.
- Session conversation memory: prior requests + resulting charts are retained for the session so "and the same for last quarter" resolves.

## Success Criteria
- [ ] "monthly total by category" adds a valid grouped chart whose figures equal the pandas aggregation over full data.
- [ ] A follow-up referencing a prior request resolves using session history.
- [ ] An un-chartable request returns a decline message, not a broken chart.
