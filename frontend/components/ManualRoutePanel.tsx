"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"
import type { ManualRoute } from "@/lib/types"
import { RouteBadge } from "@/components/RouteBadge"
import { ROUTE_LABELS, formatTime } from "@/lib/utils"

export function ManualRoutePanel({
  sourceType,
  sourceId,
  manualRoute,
  suggested,
  history,
}: {
  sourceType: string
  sourceId: string
  manualRoute: ManualRoute | null
  suggested: string[]
  history: ManualRoute[]
}) {
  const router = useRouter()
  const [routeId, setRouteId] = useState("")
  const [rationale, setRationale] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
      setRouteId("")
      setRationale("")
      router.refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`rounded-lg border bg-zinc-900 p-4 space-y-3 ${manualRoute ? "border-indigo-500/50" : "border-zinc-800"}`}>
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-zinc-200">Route decision</div>
        <span className="text-[11px] text-zinc-500">Suggested = analysis · Manual = manager</span>
      </div>

      {manualRoute ? (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] font-bold tracking-wider text-indigo-300">MANUAL ROUTE IN EFFECT</span>
            <RouteBadge routeId={manualRoute.route_id} />
            <button onClick={() => run(() => api.deleteRoute(sourceType, sourceId))} disabled={busy}
              className="ml-auto text-xs text-zinc-400 hover:text-rose-300 disabled:opacity-50">
              Reset to suggestion
            </button>
          </div>
          <p className="text-xs text-zinc-400">{manualRoute.rationale || "No rationale given"}</p>
          <p className="text-[11px] text-zinc-500">
            Set by {manualRoute.author || "manager"} · {formatTime(manualRoute.created_at)}. Survives re-imports, the update batch and restarts until reset.
          </p>
          {suggested.length > 0 && (
            <p className="text-[11px] text-zinc-500">
              Superseded suggestion: {suggested.map((s) => ROUTE_LABELS[s] ?? s).join(", ")}
            </p>
          )}
        </div>
      ) : (
        <p className="text-xs text-zinc-400">
          {suggested.length
            ? <>Using the suggested route(s): {suggested.map((s) => ROUTE_LABELS[s] ?? s).join(", ")}.</>
            : "No suggested route yet."}
        </p>
      )}

      <div className="flex gap-2 flex-wrap">
        <select value={routeId} onChange={(e) => setRouteId(e.target.value)}
          className="bg-zinc-800 border border-zinc-700 text-zinc-300 text-xs rounded h-8 px-2">
          <option value="">{manualRoute ? "Change manual route…" : "Correct the route…"}</option>
          {Object.entries(ROUTE_LABELS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select>
        <input placeholder="Why? (saved with the decision)" value={rationale} onChange={(e) => setRationale(e.target.value)}
          className="flex-1 min-w-40 bg-zinc-800 border border-zinc-700 text-zinc-300 placeholder-zinc-600 text-xs rounded h-8 px-2" />
        <button disabled={!routeId || busy}
          onClick={() => run(() => api.setRoute(sourceType, sourceId, { route_id: routeId, rationale: rationale || undefined, author: "manager" }))}
          className="h-8 px-3 text-xs rounded bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40">
          Save manual route
        </button>
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}

      {history.length > 0 && (
        <details className="text-[11px] text-zinc-500">
          <summary className="cursor-pointer">Decision history ({history.length})</summary>
          <ul className="mt-1 space-y-0.5">
            {history.map((h, i) => (
              <li key={i}>
                {formatTime(h.created_at)} · {ROUTE_LABELS[h.route_id] ?? h.route_id}
                {h.is_active ? " · active" : ` · reset ${formatTime(h.reset_at)}`}
                {h.rationale ? ` — ${h.rationale}` : ""}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
