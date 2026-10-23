"use client"
import { useState, useEffect } from "react"
import { api, API_BASE } from "@/lib/api"
import type { ExportRun } from "@/lib/types"
import { formatTime, ROUTE_LABELS } from "@/lib/utils"

type Entry = {
  source_type: string
  source_id: string
  record_ref: string
  applied_revision: number
  review_state: string
  analysis_freshness: string
  manual_override: boolean
  effective_routes: string[]
  superseded_suggested_routes: string[]
  output_paths: string[]
}

export default function ExportPage() {
  const [runs, setRuns] = useState<ExportRun[]>([])
  const [manifest, setManifest] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setRuns(await api.exportRuns())
      setManifest(await api.currentManifest())
    } catch {
      setManifest(null)
    }
  }
  useEffect(() => { load() }, [])

  const generate = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.triggerExport()
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed")
    } finally {
      setBusy(false)
    }
  }

  const entries = (manifest?.entries as Entry[] | undefined) ?? []

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Export</h1>
          <p className="text-xs text-zinc-500 mt-1">
            Writes a versioned bundle of the current state: a dossier per record, one file per active route, the manager brief,
            and manifest.json / manifest.csv. The newest bundle is marked current.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={generate} disabled={busy}
            className="h-9 px-4 text-sm rounded bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-50">
            {busy ? "Generating…" : "Generate export"}
          </button>
          {manifest && (
            <a href={`${API_BASE}/export/current/zip`}
              className="h-9 px-4 text-sm rounded border border-zinc-600 text-zinc-200 hover:text-white flex items-center">
              Download current bundle (.zip)
            </a>
          )}
        </div>
      </div>
      {error && <div className="text-sm text-red-400">{error}</div>}

      {manifest && (
        <div className="rounded-lg border border-indigo-500/40 bg-zinc-900 p-4 space-y-3">
          <div className="text-sm text-zinc-200">
            Current bundle <span className="font-mono text-indigo-300">{String(manifest.bundle)}</span> ·{" "}
            {formatTime(String(manifest.generated_at))}
          </div>
          <div className="text-xs text-zinc-400">
            {String(manifest.record_count)} records · {String(manifest.usable_text_count)} with text ·{" "}
            {String(manifest.route_assignment_count)} route outputs · {String(manifest.manual_override_count)} manual override(s)
          </div>
          <pre className="text-[11px] text-zinc-400 bg-zinc-950 rounded p-3 overflow-x-auto">{`${String(manifest.bundle)}/
├── README.md
├── manifest.json            one entry per record
├── manifest.csv             one row per output file
├── manager_brief_2026-08-21.md
├── records/<ref>_<type>_<source_id>.md      all ${String(manifest.record_count)} records
└── routes/
${Object.values((manifest.routes as Record<string, { folder: string; label: string }>) ?? {})
  .map((r) => `    ├── ${r.folder.replace("routes/", "")}/   ${r.label}`).join("\n")}`}</pre>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-zinc-500 text-left">
                <tr>
                  <th className="font-normal py-1">Record</th><th className="font-normal">Rev</th><th className="font-normal">State</th>
                  <th className="font-normal">Effective routes</th><th className="font-normal">Manual</th><th className="font-normal">Output paths</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.source_id} className="border-t border-zinc-800 align-top">
                    <td className="py-1 font-mono text-zinc-300">{e.record_ref}</td>
                    <td className="text-zinc-400">{e.applied_revision}</td>
                    <td className="text-zinc-400">{e.review_state}<div className="text-zinc-600">{e.analysis_freshness}</div></td>
                    <td className="text-zinc-300">
                      {e.effective_routes.map((r) => ROUTE_LABELS[r] ?? r).join(", ") || "—"}
                      {e.superseded_suggested_routes.length > 0 && (
                        <div className="text-zinc-600">superseded: {e.superseded_suggested_routes.join(", ")}</div>
                      )}
                    </td>
                    <td className={e.manual_override ? "text-indigo-300" : "text-zinc-600"}>{e.manual_override ? "yes" : "no"}</td>
                    <td className="font-mono text-[10px] text-zinc-500">{e.output_paths.map((p) => <div key={p}>{p}</div>)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div>
        <h2 className="text-sm text-zinc-400 mb-2">Export history</h2>
        <ul className="space-y-1 text-xs">
          {runs.map((r) => (
            <li key={r.id} className="flex gap-3 text-zinc-500">
              <span className={r.is_current ? "text-indigo-300" : ""}>{r.is_current ? "CURRENT" : "superseded"}</span>
              <span>{formatTime(r.created_at)}</span>
              <span className="font-mono truncate">{r.bundle_path}</span>
            </li>
          ))}
          {runs.length === 0 && <li className="text-zinc-600">No exports yet.</li>}
        </ul>
      </div>
    </div>
  )
}
