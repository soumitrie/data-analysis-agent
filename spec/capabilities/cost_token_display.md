# Capability: Cost & Token Display

**Phase 2.** Deferred — Phase-1 UI shows a greyed "Token usage & cost (Phase 2)" stub (values are already logged in Phase 1).

## What It Does
Surfaces the per-analysis Gemini token counts and estimated cost in the UI.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| usage (prompt/completion tokens) | JSON | analyze/ask response (captured from Phase 1) | yes |
| cost rates | env | `AGENT_LLM_INPUT_COST_PER_1K` / `_OUTPUT_COST_PER_1K` | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| tokens + estimated_cost_usd | JSON | cost/token panel in UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| (none — reads captured usage) | | cost shown as "n/a" if rates unset |

## Business Rules
- Tokens come from Gemini `usage_metadata`; cost = tokens/1000 × configured rate.
- If rates are unset, show tokens with cost "n/a" (never a fabricated cost).

## Success Criteria
- [ ] The panel shows real prompt/completion token counts for the last analysis.
- [ ] Cost is computed from configured rates, or "n/a" when unset.
