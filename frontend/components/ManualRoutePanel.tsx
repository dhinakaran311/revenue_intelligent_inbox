"use client"
import { useState } from "react"
import { api } from "@/lib/api"
import type { ManualRoute } from "@/lib/types"
import { RouteBadge } from "@/components/RouteBadge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ROUTE_LABELS, formatDate } from "@/lib/utils"

interface ManualRoutePanelProps {
  sourceType: string
  sourceId: string
  initialManualRoute: ManualRoute | null
}

export function ManualRoutePanel({
  sourceType,
  sourceId,
  initialManualRoute,
}: ManualRoutePanelProps) {
  const [manualRoute, setManualRoute] = useState<ManualRoute | null>(
    initialManualRoute
  )
  const [routeId, setRouteId] = useState("")
  const [rationale, setRationale] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSet = async () => {
    if (!routeId) return
    setLoading(true)
    setError(null)
    try {
      const result = await api.setRoute(sourceType, sourceId, {
        route_id: routeId,
        rationale: rationale || undefined,
        author: "manager",
      })
      setManualRoute(result)
      setRouteId("")
      setRationale("")
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to set route")
    } finally {
      setLoading(false)
    }
  }

  const handleReset = async () => {
    setLoading(true)
    setError(null)
    try {
      await api.deleteRoute(sourceType, sourceId)
      setManualRoute(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to reset route")
    } finally {
      setLoading(false)
    }
  }

  if (manualRoute?.is_active) {
    return (
      <div className="rounded-lg border-l-4 border-l-indigo-500 border border-zinc-800 bg-zinc-900 p-5">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-indigo-400 tracking-wide">
              MANUAL ROUTE
            </span>
            <RouteBadge routeId={manualRoute.route_id} />
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReset}
            disabled={loading}
            className="text-zinc-500 hover:text-red-400 h-6 text-xs"
          >
            Reset
          </Button>
        </div>
        <p className="text-xs text-zinc-400">
          {manualRoute.rationale || "No rationale provided"}
        </p>
        <p className="text-xs text-zinc-600 mt-1">
          Set by {manualRoute.author || "unknown"} · {formatDate(manualRoute.created_at)}
        </p>
        {error && <p className="text-xs text-red-400 mt-2">{error}</p>}
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
      <div className="text-xs text-zinc-500 mb-3">Set a manual route override</div>
      <div className="flex gap-2 flex-wrap">
        <Select value={routeId} onValueChange={setRouteId}>
          <SelectTrigger className="w-48 bg-zinc-800 border-zinc-700 text-zinc-300 text-xs h-8">
            <SelectValue placeholder="Select route…" />
          </SelectTrigger>
          <SelectContent className="bg-zinc-900 border-zinc-700">
            {Object.entries(ROUTE_LABELS).map(([id, label]) => (
              <SelectItem key={id} value={id} className="text-zinc-300 text-xs">
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          placeholder="Rationale (optional)"
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          className="flex-1 min-w-40 bg-zinc-800 border-zinc-700 text-zinc-300 placeholder-zinc-600 text-xs h-8"
        />
        <Button
          onClick={handleSet}
          disabled={!routeId || loading}
          size="sm"
          className="h-8 text-xs bg-indigo-600 hover:bg-indigo-500"
        >
          Set Route
        </Button>
      </div>
      {error && <p className="text-xs text-red-400 mt-2">{error}</p>}
    </div>
  )
}
