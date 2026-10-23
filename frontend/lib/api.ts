import type {
  DashboardMetrics,
  RecordRow,
  RecordDetail,
  Analysis,
  Evidence,
  ManualRoute,
  ExportRun,
} from "./types"

const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const body = await res.json()
      msg = body?.detail ?? body?.message ?? msg
    } catch {}
    throw new Error(msg)
  }
  return res.json() as Promise<T>
}

export const api = {
  dashboard: () =>
    fetchJSON<DashboardMetrics>(`${BASE}/metrics/dashboard`),

  definitions: () =>
    fetchJSON<Record<string, string>>(`${BASE}/definitions`),

  records: (params?: URLSearchParams) =>
    fetchJSON<RecordRow[]>(`${BASE}/records?${params?.toString() ?? ""}`),

  recordDetail: (type: string, id: string) =>
    fetchJSON<RecordDetail>(
      `${BASE}/records/${encodeURIComponent(type)}/${encodeURIComponent(id)}`
    ),

  recordAnalysis: (type: string, id: string) =>
    fetchJSON<Analysis>(
      `${BASE}/records/${encodeURIComponent(type)}/${encodeURIComponent(id)}/analysis`
    ),

  recordEvidence: (type: string, id: string) =>
    fetchJSON<Evidence>(
      `${BASE}/records/${encodeURIComponent(type)}/${encodeURIComponent(id)}/evidence`
    ),

  setRoute: (
    type: string,
    id: string,
    body: { route_id: string; rationale?: string; author?: string }
  ) =>
    fetchJSON<ManualRoute>(
      `${BASE}/records/${encodeURIComponent(type)}/${encodeURIComponent(id)}/route`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    ),

  deleteRoute: (type: string, id: string) =>
    fetchJSON<{ ok: boolean }>(
      `${BASE}/records/${encodeURIComponent(type)}/${encodeURIComponent(id)}/route`,
      { method: "DELETE" }
    ),

  triggerExport: () =>
    fetchJSON<{
      run_id: string
      bundle_path: string
      manifest_path: string
      record_count: number
      manifest_entry_count: number
      generated_at: string
    }>(`${BASE}/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }),

  exportRuns: () => fetchJSON<ExportRun[]>(`${BASE}/export-runs`),
}
