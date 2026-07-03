# Capability: Executive Summary

**Phase 3.** Deferred.

## What It Does
Tops the auto-pack with a written "Key findings" executive summary — a few sharp, IB-tone sentences drawn from the aggregated profile and computed chart summaries.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| profile + computed chart summaries | JSON | prior nodes | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| summary prose | str | exec-summary block above the pack; stored on AnalysisRun |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Google Gemini | `write_summary` from aggregates + computed summaries only | omit the summary block (pack still renders), log |

## Business Rules
- The summary is written only from aggregates and locally-computed figures — never from raw rows, never inventing numbers.
- Any number cited must trace to a computed figure.

## Success Criteria
- [ ] The summary references only figures present in the computed pack.
- [ ] A Gemini failure omits the summary without breaking the pack.
