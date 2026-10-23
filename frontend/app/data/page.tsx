"use client"
import { useEffect, useState } from "react"
import Link from "next/link"
import { api } from "@/lib/api"
import type { ImportRun } from "@/lib/types"
import { formatTime } from "@/lib/utils"

type Counts = { records: number; usable: number; m07rev: number | null; m07manual: string | null; m07analysis: string | null }

export default function DataPage() {
  const [runs, setRuns] = useState<ImportRun[]>([])
  const [counts, setCounts] = useState<Counts | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [log, setLog] = useState<string[]>([])

  const refresh = async () => {
    try {
      const [r, recs] = await Promise.all([api.importRuns(), api.records()])
      setRuns(r)
      const m07 = recs.find((x) => x.record_ref === "M07" && x.source_type === "meeting")
      setCounts({
        records: recs.length,
        usable: recs.filter((x) => x.has_usable_text).length,
        m07rev: m07?.revision ?? null,
        m07manual: m07?.manual_route_id ?? null,
        m07analysis: m07 ? m07.analysis_state : null,
      })
    } catch (e) {
      setLog((l) => [`Error: ${e instanceof Error ? e.message : e}`, ...l])
    }
  }
  useEffect(() => { refresh() }, [])

  const step = async (label: string, fn: () => Promise<unknown>) => {
    if (label === "Reset" && !confirm("Delete all imported records, analyses, manual routes and export history?")) return
    setBusy(label)
    try {
      const res = (await fn()) as Record<string, unknown>
      const summary = "accepted" in res
        ? `accepted ${res.accepted}, replaced ${res.replaced}, ignored ${res.ignored}, errors ${(res.errors as unknown[])?.length ?? 0}`
        : JSON.stringify(res).slice(0, 220)
      setLog((l) => [`${new Date().toLocaleTimeString()} · ${label}: ${summary}`, ...l])
    } catch (e) {
      setLog((l) => [`${label} failed: ${e instanceof Error ? e.message : e}`, ...l])
    } finally {
      setBusy(null)
      refresh()
    }
  }

  const btn = "h-9 px-3 text-xs rounded border border-zinc-700 text-zinc-200 hover:border-indigo-500 hover:text-white disabled:opacity-40 text-left"

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-zinc-100">Data &amp; replay</h1>
        <p className="text-xs text-zinc-500 mt-1">
          Imports use the supplied deliveries. Identity is (source_type, source_id); a record is replaced only by a higher revision.
          Manual routes are never touched by imports.
        </p>
      </div>

      {counts && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            ["Unique records", counts.records, "Expect 44 throughout"],
            ["Usable texts", counts.usable, "17 after initial, 18 after update"],
            ["M07 revision", counts.m07rev ?? "—", `analysis: ${counts.m07analysis ?? "—"}`],
            ["M07 manual route", counts.m07manual ?? "none", "must survive update + restart"],
          ].map(([k, v, s]) => (
            <div key={String(k)} className="rounded-lg border border-zinc-800 bg-zinc-900 p-3">
              <div className="text-[11px] text-zinc-500">{k}</div>
              <div className="text-xl text-zinc-100 font-semibold">{String(v)}</div>
              <div className="text-[11px] text-zinc-500">{s}</div>
            </div>
          ))}
        </div>
      )}

      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 space-y-3">
        <div className="text-sm font-medium text-zinc-200">Replay steps</div>
        <div className="grid md:grid-cols-2 gap-2">
          <button disabled={!!busy} className={btn} onClick={() => step("Reset", api.reset)}>0 · Clean start (reset all app data)</button>
          <button disabled={!!busy} className={btn} onClick={() => step("Import initial", () => api.importSample("initial"))}>1 · Import 01_initial.json</button>
          <button disabled={!!busy} className={btn} onClick={() => step("Re-import initial (reordered)", () => api.importSample("initial", true))}>2 · Import 01_initial.json again, reversed order</button>
          <Link href="/inbox?source_type=meeting" className={`${btn} flex items-center`}>3 · Set a manual route on M07 (open M07 in the inbox) →</Link>
          <button disabled={!!busy} className={btn} onClick={() => step("Import update", () => api.importSample("update"))}>4 · Import 02_update.json (M07 revision 2)</button>
          <button disabled={!!busy} className={btn} onClick={() => step("Re-import initial", () => api.importSample("initial"))}>5 · Import 01_initial.json again (rev 1 must be ignored)</button>
          <button disabled={!!busy} className={btn} onClick={() => step("Apply reviewed analyses", api.applyAllPrepared)}>6 · Apply reviewed analyses matching current revisions</button>
          <Link href="/export" className={`${btn} flex items-center`}>7 · Generate and inspect an export →</Link>
        </div>
        <div className="pt-2 border-t border-zinc-800 flex flex-wrap items-center gap-2">
          <label className="text-xs text-zinc-400">Or upload a delivery file (01_initial.json / 02_update.json):</label>
          <input type="file" accept="application/json,.json" disabled={!!busy}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) step(`Upload ${f.name}`, () => api.uploadDelivery(f)); e.target.value = "" }}
            className="text-xs text-zinc-400 file:mr-2 file:h-8 file:px-3 file:rounded file:border-0 file:bg-zinc-700 file:text-zinc-100" />
        </div>
        <div className="pt-2 border-t border-zinc-800">
          <button disabled={!!busy} onClick={() => step("Demo load", api.demoLoad)}
            className="h-9 px-4 text-xs rounded bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40">
            {busy === "Demo load" ? "Loading…" : "One-click demo load: reset → initial → update → reviewed analyses"}
          </button>
        </div>
        {busy && <p className="text-xs text-zinc-400">{busy}…</p>}
        {log.length > 0 && (
          <ul className="text-[11px] font-mono text-zinc-400 space-y-0.5 max-h-40 overflow-y-auto">
            {log.map((l, i) => <li key={i}>{l}</li>)}
          </ul>
        )}
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
        <div className="text-sm font-medium text-zinc-200">Import history (audit, not activity)</div>
        <table className="w-full text-xs mt-2">
          <thead className="text-zinc-500 text-left">
            <tr><th className="font-normal py-1">When</th><th className="font-normal">File</th><th className="font-normal text-right">Total</th><th className="font-normal text-right">Accepted</th><th className="font-normal text-right">Replaced</th><th className="font-normal text-right">Ignored</th><th className="font-normal text-right">Errors</th></tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id} className="border-t border-zinc-800 text-zinc-300">
                <td className="py-1">{formatTime(r.received_at)}</td>
                <td>{r.filename ?? "(api body)"}</td>
                <td className="text-right">{r.total_records}</td>
                <td className="text-right">{r.accepted}</td>
                <td className="text-right">{r.replaced}</td>
                <td className="text-right">{r.ignored}</td>
                <td className="text-right">{r.error_count}</td>
              </tr>
            ))}
            {runs.length === 0 && <tr><td colSpan={7} className="py-2 text-zinc-600">No imports yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}
