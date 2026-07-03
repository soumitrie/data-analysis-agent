# Capability: Data-Quality Flags

**Phase 3.** Deferred.

## What It Does
Runs a local profiling pass that flags data-quality issues (nulls, duplicates, mixed types, out-of-range/unparseable dates, negative-where-unexpected) and surfaces them in a quality panel.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataframe | in-memory | DatasetStore | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| quality flags (type, column, count, severity) | JSON | data-quality panel in UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| pandas | null/dup/type/range checks over full data | log; panel shows what computed |

## Business Rules
- Purely local/deterministic — no LLM. Counts are exact over full data.
- Flags are informational; they never block chart rendering.

## Success Criteria
- [ ] Nulls/duplicates seeded in the sample CSV are counted exactly.
- [ ] The panel lists each flag with its column and count.
