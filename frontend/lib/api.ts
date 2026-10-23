import type {
  DashboardMetrics,
  RecordRow,
  RecordDetail,
  Evidence,
  ManualRoute,
  ExportRun,
  Brief,
  ImportRun,
} from "./types"

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...init })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const body = await res.json()
      const d = body?.detail ?? body?.message
      msg = typeof d === "string" ? d : d?.message ?? JSON.stringify(d) ?? msg
    } catch {}
    throw new Error(msg)
  }
  return res.json() as Promise<T>
}

const post = <T,>(path: string, body?: unknown) =>
  fetchJSON<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  })

const rec = (type: string, id: string) =>
  `/records/${encodeURIComponent(type)}/${encodeURIComponent(id)}`

export const api = {
  dashboard: (params?: URLSearchParams) =>
    fetchJSON<DashboardMetrics>(`/metrics/dashboard?${params?.toString() ?? ""}`),
  records: (params?: URLSearchParams) =>
    fetchJSON<RecordRow[]>(`/records?${params?.toString() ?? ""}`),
  recordDetail: (type: string, id: string) => fetchJSON<RecordDetail>(rec(type, id)),
  recordEvidence: (type: string, id: string) => fetchJSON<Evidence>(`${rec(type, id)}/evidence`),
  setRoute: (type: string, id: string, body: { route_id: string; rationale?: string; author?: string }) =>
    post<{ manual_route: ManualRoute }>(`${rec(type, id)}/route`, body),
  deleteRoute: (type: string, id: string) =>
    fetchJSON<{ deactivated_count: number }>(`${rec(type, id)}/route`, { method: "DELETE" }),
  applyPrepared: (type: string, id: string) => post<{ status: string }>(`${rec(type, id)}/analysis/prepared`),
  runtimeAnalysis: (type: string, id: string) => post<{ status: string }>(`${rec(type, id)}/analysis/refresh`),
  brief: () => fetchJSON<Brief>(`/brief`),
  triggerExport: () =>
    post<{
      run_id: string
      bundle: string
      record_count: number
      output_file_count: number
      route_assignment_count: number
      manual_override_count: number
      generated_at: string
    }>(`/export`),
  exportRuns: () => fetchJSON<ExportRun[]>(`/export-runs`),
  currentManifest: () => fetchJSON<Record<string, unknown>>(`/export/current`),
  importRuns: () => fetchJSON<ImportRun[]>(`/import-runs`),
  importSample: (name: "initial" | "update", reorder = false) =>
    post<Record<string, unknown>>(`/admin/import-sample/${name}?reorder=${reorder}`),
  uploadDelivery: (file: File) => {
    const fd = new FormData()
    fd.append("file", file)
    return fetchJSON<Record<string, unknown>>(`/import/upload`, { method: "POST", body: fd })
  },
  reset: () => post<Record<string, unknown>>(`/admin/reset`),
  demoLoad: () => post<Record<string, unknown>>(`/admin/demo-load`),
  applyAllPrepared: () => post<{ results: Record<string, string[]> }>(`/admin/apply-prepared`),
}
