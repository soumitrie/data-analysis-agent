// Shapes consumed from spec/api.md. The frontend depends ONLY on these.

export interface ApiEnvelope<T> {
  data: T | null
  error: ApiError | null
}

export interface ApiError {
  code: string
  message: string
}

export interface ColumnPreview {
  name: string
  dtype: string
  sample_values: string[]
}

export interface Dataset {
  dataset_id: string
  filename: string
  row_count: number
  column_count: number
  columns: ColumnPreview[]
}

export interface ColumnMapping {
  date: string | null
  amount: string | null
  category: string | null
  counterparty: string | null
  assumption_note: string
}

export interface AmountSummary {
  sum: number
  mean: number
  min: number
  max: number
}

export interface DateRange {
  start: string | null
  end: string | null
}

export interface AnalysisProfile {
  row_count: number
  date_range?: DateRange | null
  amount_summary?: AmountSummary | null
}

// A Plotly figure: data traces + layout. Rendered directly by react-plotly.js.
export interface PlotlyFigure {
  // Kept loose on purpose — the server applies the full IB house-style layout.
  data: Record<string, unknown>[]
  layout: Record<string, unknown>
}

export interface ChartSpec {
  id: string
  type: string
  title: string
  subtitle?: string | null
  figure: PlotlyFigure
  computed_summary?: Record<string, unknown> | null
  rationale?: string | null
}

export interface Usage {
  prompt_tokens?: number | null
  completion_tokens?: number | null
  estimated_cost_usd?: number | null
}

export interface AnalysisResult {
  run_id: string
  dataset_id: string
  status: string
  column_mapping: ColumnMapping
  profile?: AnalysisProfile | null
  charts: ChartSpec[]
  usage?: Usage | null
  elapsed_ms?: number | null
}
