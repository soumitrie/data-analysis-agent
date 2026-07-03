# Capability: Session Persistence & Reopen

**Phase 4.** Deferred — Phase-1 History panel is a labelled stub.

## What It Does
Persists analyses server-side and lets the user reopen a past analysis from a History panel across sessions.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| run_id | str | History panel (`GET /api/runs/{id}`) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| history list (run_id, filename, created_at, status) | JSON | History panel |
| reopened analysis (mapping + chart specs) | JSON | main view |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | list/read `AnalysisRun` + `chart_specs` | 404 if run missing |

## Business Rules
- `AnalysisRun` + `chart_specs` (plan only, no raw data) persist across restarts.
- Reopening recomputes figures from the stored plan if the dataset is still in memory; if the dataset was evicted, prompt re-upload (charts need the local data to recompute exact figures).

## Success Criteria
- [ ] Past analyses appear in the History panel after a restart.
- [ ] Reopening a run restores its mapping and chart plan; figures recompute when the dataset is available.
