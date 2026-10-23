"use client"
import type { Evidence } from "@/lib/types"

export function EvidencePanel({
  evidence,
  hasUsableText,
}: {
  evidence: Evidence
  hasUsableText: boolean
}) {
  if (!evidence.found || !evidence.evidence?.length) {
    return (
      <details className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
        <summary className="cursor-pointer text-xs text-zinc-500 hover:text-zinc-300">
          Evidence citations
        </summary>
        <p className="text-xs text-zinc-600 mt-2">
          No evidence citations available.
        </p>
      </details>
    )
  }

  return (
    <details open={hasUsableText} className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <summary className="cursor-pointer text-xs text-zinc-500 hover:text-zinc-300">
        Evidence citations ({evidence.evidence.length})
      </summary>
      <div className="mt-3 space-y-2">
        {evidence.evidence.map((e, i) =>
          e.type === "call_transcript_snippet" ? (
            <blockquote
              key={i}
              className="border-l-2 border-zinc-600 pl-3 font-mono text-xs text-zinc-300 py-1"
            >
              {e.quote}
            </blockquote>
          ) : (
            <div key={i} className="text-xs">
              <span className="text-zinc-500">
                Turn {e.turn_number} · {e.speaker}:
              </span>
              <span className="font-mono text-zinc-300 ml-2">{e.quote}</span>
            </div>
          )
        )}
      </div>
    </details>
  )
}
