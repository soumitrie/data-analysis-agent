# Capability: Static Publication Export

**Phase 4.** Deferred — Phase-1 export buttons are labelled stubs.

## What It Does
Exports individual charts as high-res PNG/SVG and the full pack as a slide-ready bundle, all in the IB house style with slide-ready sizing.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id, chart id, format | str | UI (`GET .../export?format=png\|svg`) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| PNG/SVG file | binary | browser download |
| pack bundle | zip | browser download; saved server-side |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Plotly + Kaleido | render figure to static image at slide-ready dimensions | 500 with clear message |
| filesystem | save pack bundle server-side | log; still stream download |

## Business Rules
- Static images use the identical house-style template as the interactive charts.
- Slide-ready sizing (`Assumed:` 16:9 at a fixed high-res DPI).

## Success Criteria
- [ ] A chart downloads as a valid high-res PNG and SVG matching the on-screen chart.
- [ ] The full-pack bundle contains one image per chart and is saved server-side.
