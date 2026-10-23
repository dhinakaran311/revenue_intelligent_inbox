"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"

export function AnalysisActions({ sourceType, sourceId }: { sourceType: string; sourceId: string }) {
  const router = useRouter()
  const [busy, setBusy] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  const run = async (label: string, fn: () => Promise<{ status: string }>) => {
    setBusy(label)
    setMsg(null)
    try {
      const r = await fn()
      setMsg(`Done: ${r.status}`)
      router.refresh()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed")
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button disabled={!!busy} onClick={() => run("prepared", () => api.applyPrepared(sourceType, sourceId))}
        className="h-8 px-3 text-xs rounded bg-amber-600 hover:bg-amber-500 text-white disabled:opacity-50">
        {busy === "prepared" ? "Applying…" : "Apply reviewed analysis for this revision"}
      </button>
      <button disabled={!!busy} onClick={() => run("runtime", () => api.runtimeAnalysis(sourceType, sourceId))}
        className="h-8 px-3 text-xs rounded border border-zinc-600 text-zinc-300 hover:text-white disabled:opacity-50">
        {busy === "runtime" ? "Generating…" : "Generate runtime analysis (Groq)"}
      </button>
      {msg && <span className="text-xs text-zinc-400">{msg}</span>}
    </div>
  )
}
