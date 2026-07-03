import type { AnalysisResult, ApiEnvelope, Dataset } from './types'

// Same-origin calls. The app is served under basePath '/app', but the FastAPI
// routes live at '/api/...' (root), so we use absolute '/api/...' URLs — NOT
// '/app/api/...'. Verified against spec/api.md.
const API_BASE = '/api'

export class ApiRequestError extends Error {
  status: number
  code: string
  constructor(status: number, message: string, code = 'error') {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
    this.code = code
  }
}

async function parseEnvelope<T>(res: Response): Promise<T> {
  let body: ApiEnvelope<T> | { detail?: { message?: string; code?: string } } | null = null
  try {
    body = await res.json()
  } catch {
    body = null
  }

  if (!res.ok) {
    // FastAPI HTTPException uses { detail: {...} }; the skeleton envelope uses
    // { error: {...} }. Handle both, prefer a human message.
    const envelope = body as ApiEnvelope<T> | null
    const detail = (body as { detail?: { message?: string; code?: string } } | null)?.detail
    const message =
      envelope?.error?.message ??
      detail?.message ??
      (typeof detail === 'string' ? detail : undefined) ??
      `Request failed (${res.status})`
    const code = envelope?.error?.code ?? detail?.code ?? String(res.status)
    throw new ApiRequestError(res.status, message, code)
  }

  const envelope = body as ApiEnvelope<T> | null
  if (envelope?.error) {
    throw new ApiRequestError(res.status, envelope.error.message, envelope.error.code)
  }
  if (!envelope || envelope.data == null) {
    throw new ApiRequestError(res.status, 'Empty response from server', 'empty')
  }
  return envelope.data
}

/** Upload a CSV file (multipart, field `file`). No LLM call — fast. */
export async function uploadDataset(file: File): Promise<Dataset> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/datasets`, {
    method: 'POST',
    body: form,
  })
  return parseEnvelope<Dataset>(res)
}

/** Run the auto chart-pack analysis for a previously-uploaded dataset. */
export async function analyzeDataset(datasetId: string): Promise<AnalysisResult> {
  const res = await fetch(`${API_BASE}/datasets/${encodeURIComponent(datasetId)}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  return parseEnvelope<AnalysisResult>(res)
}

/** Human-readable message for a caught error, matching spec/ui.md error states. */
export function messageForError(err: unknown): string {
  if (err instanceof ApiRequestError) {
    switch (err.status) {
      case 400:
        return err.message || "Couldn't parse that CSV — check the file."
      case 404:
        return 'This dataset expired — please re-upload the file.'
      case 413:
        return 'That file is too large to upload.'
      case 422:
        return 'No numeric column found to chart — this file may not be transactional.'
      case 500:
      case 502:
        return 'Chart planning failed — please retry.'
      default:
        return err.message || 'Something went wrong — please try again.'
    }
  }
  if (err instanceof TypeError) {
    // fetch network failure
    return 'Network error — is the server running?'
  }
  return 'Network error — is the server running?'
}
