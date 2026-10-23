"use client"
import { useState, useEffect } from "react"
import { api } from "@/lib/api"
import type { ExportRun } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatDate } from "@/lib/utils"

export default function ExportPage() {
  const [runs, setRuns] = useState<ExportRun[]>([])
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<{
    bundle_path: string
    manifest_path: string
    record_count: number
    manifest_entry_count: number
    generated_at: string
  } | null>(null)

  const loadRuns = async () => {
    setLoading(true)
    try {
      const data = await api.exportRuns()
      setRuns(data)
    } catch {
      setError("Could not load export runs")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRuns()
  }, [])

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const result = await api.triggerExport()
      setLastResult(result)
      await loadRuns()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Export failed")
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-100">Export Bundle</h1>
        <Button
          onClick={handleGenerate}
          disabled={generating}
          className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm"
        >
          {generating ? "Generating…" : "Generate Export"}
        </Button>
      </div>

      {error && (
        <div className="text-sm text-red-400 bg-red-950/30 border border-red-800/50 rounded px-4 py-3">
          {error}
        </div>
      )}

      {lastResult && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-green-400">✓ Export Generated</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-xs">
            <div>
              <span className="text-zinc-500">Records: </span>
              <span className="text-zinc-200">{lastResult.record_count}</span>
            </div>
            <div>
              <span className="text-zinc-500">Manifest entries: </span>
              <span className="text-zinc-200">{lastResult.manifest_entry_count}</span>
            </div>
            <div>
              <span className="text-zinc-500">Generated: </span>
              <span className="text-zinc-200">{lastResult.generated_at}</span>
            </div>
            <div className="font-mono text-zinc-500 mt-2 break-all">{lastResult.bundle_path}</div>
          </CardContent>
        </Card>
      )}

      <div>
        <h2 className="text-sm font-medium text-zinc-400 mb-3">Past Runs</h2>
        {loading ? (
          <div className="text-xs text-zinc-500">Loading…</div>
        ) : runs.length === 0 ? (
          <div className="text-xs text-zinc-600">No export runs yet.</div>
        ) : (
          <div className="space-y-2">
            {runs.map((run) => (
              <Card
                key={run.id}
                className={`bg-zinc-900 border-zinc-800 ${
                  run.is_current ? "border-indigo-500/50" : ""
                }`}
              >
                <CardContent className="px-4 py-3 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      {run.is_current && (
                        <span className="text-xs text-indigo-400 font-medium">CURRENT</span>
                      )}
                      <span className="font-mono text-xs text-zinc-500">{run.id?.slice(0, 8)}…</span>
                    </div>
                    <div className="font-mono text-xs text-zinc-600 break-all">
                      {run.bundle_path}
                    </div>
                  </div>
                  <span className="text-xs text-zinc-500 shrink-0 ml-4">
                    {formatDate(run.created_at)}
                  </span>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
