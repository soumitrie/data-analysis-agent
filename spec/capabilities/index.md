# Capabilities Index — Ledger Lens

> One file per discrete capability. No number prefix. Each maps to a phase in `spec/roadmap.md`.

## Capabilities in This Project

| Capability | Phase | File |
|-----------|-------|------|
| Transaction chart pack (upload → auto 3-chart pack) | 1 | [transaction_chart_pack.md](transaction_chart_pack.md) |
| NL chart requests | 2 | [nl_chart_requests.md](nl_chart_requests.md) |
| Aggregated data table view | 2 | [aggregated_data_table.md](aggregated_data_table.md) |
| Cost & token display | 2 | [cost_token_display.md](cost_token_display.md) |
| Full chart arsenal | 3 | [full_chart_arsenal.md](full_chart_arsenal.md) |
| Executive summary | 3 | [executive_summary.md](executive_summary.md) |
| Data-quality flags | 3 | [data_quality_flags.md](data_quality_flags.md) |
| Proactive insights & follow-ups | 4 | [proactive_insights.md](proactive_insights.md) |
| Static publication export | 4 | [static_publication_export.md](static_publication_export.md) |
| Session persistence & reopen | 4 | [session_persistence.md](session_persistence.md) |

## Phase-to-capability map

- **Phase 1:** transaction_chart_pack (the full primary journey, first-time-right).
- **Phase 2 (Ask + Observe):** nl_chart_requests, aggregated_data_table, cost_token_display.
- **Phase 3 (Full Arsenal + Narrative):** full_chart_arsenal, executive_summary, data_quality_flags.
- **Phase 4 (Proactive + Export + Persistence):** proactive_insights, static_publication_export, session_persistence.

## How to Add a New Capability

Run `/zero-shot-build [description]`. The spec-writer creates `<name>.md`, updates this index, flags dependencies, and self-reviews fit against the architecture, agent graph, and data model.
