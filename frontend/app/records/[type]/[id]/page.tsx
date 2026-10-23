import Link from "next/link"
import { api } from "@/lib/api"
import { RouteBadge } from "@/components/RouteBadge"
import { SourceTypeBadge } from "@/components/SourceTypeBadge"
import { PersonRoleChip } from "@/components/PersonRoleChip"
import { FreshnessChip } from "@/components/FreshnessChip"
import { ManualRoutePanel } from "@/components/ManualRoutePanel"
import { EvidencePanel } from "@/components/EvidencePanel"
import { formatDate } from "@/lib/utils"

export const dynamic = "force-dynamic"

export default async function RecordDetailPage({
  params,
}: {
  params: { type: string; id: string }
}) {
  const { type, id } = params
  const decodedId = decodeURIComponent(id)

  let record, analysis, evidence
  try {
    ;[record, analysis, evidence] = await Promise.all([
      api.recordDetail(type, decodedId),
      api.recordAnalysis(type, decodedId).catch(() => null),
      api.recordEvidence(type, decodedId).catch(() => null),
    ])
  } catch {
    return (
      <div className="text-red-400 text-sm p-4">
        Could not load record — is the backend running?
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <Link
        href="/inbox"
        className="text-xs text-zinc-500 hover:text-zinc-300 inline-block mb-2"
      >
        ← Back to Inbox
      </Link>

      {/* Header */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <SourceTypeBadge type={record.source_type} />
              <span className="font-semibold text-zinc-100">{record.record_ref ?? record.source_id}</span>
              <span className="text-xs text-zinc-500">rev {record.revision}</span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <span className="text-zinc-300">{record.person_name ?? "—"}</span>
              <PersonRoleChip role={record.person_role} />
              <span className="text-zinc-500">{formatDate(record.activity_date)}</span>
            </div>
            <div className="font-mono text-xs text-zinc-600 mt-1">{record.source_id}</div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <FreshnessChip state={record.analysis_state} />
            {analysis?.analysis_source && (
              <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                {analysis.analysis_source.toUpperCase()}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* No-text state */}
      {!record.has_usable_text && (
        <div className="rounded-lg border border-amber-800/50 bg-amber-950/30 p-5 flex gap-3">
          <span className="text-amber-400 text-xl">⊘</span>
          <div>
            <div className="font-medium text-amber-300">No usable supplied text</div>
            <div className="text-sm text-amber-400/70 mt-1">
              Analysis unavailable. Source metadata only. No inference is made about this record.
            </div>
          </div>
        </div>
      )}

      {/* Analysis section */}
      {record.has_usable_text && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5 space-y-4">
          {analysis?.freshness_label === "stale" && (
            <div className="text-xs text-amber-400 bg-amber-950/30 border border-amber-800/50 rounded px-3 py-2">
              ⚠ Analysis based on revision {analysis.source_revision} — text has changed
            </div>
          )}

          <p className="text-zinc-100 text-sm leading-relaxed">
            {analysis?.concise_output ?? "Analysis pending."}
          </p>

          <details className="text-sm">
            <summary className="cursor-pointer text-zinc-400 hover:text-zinc-200">
              Analysis details
            </summary>
            <div className="mt-3 space-y-3 text-zinc-300">
              <div>
                <div className="text-xs text-zinc-500 mb-1">WHAT THIS ESTABLISHES</div>
                {analysis?.what_established ?? "—"}
              </div>
              <div>
                <div className="text-xs text-zinc-500 mb-1">WHAT IT DOES NOT ESTABLISH</div>
                {analysis?.what_not_established ?? "—"}
              </div>
              <div>
                <div className="text-xs text-zinc-500 mb-1">NEXT ACTION</div>
                {analysis?.next_action ?? "—"}
              </div>
              {analysis?.owner && (
                <div>
                  <div className="text-xs text-zinc-500 mb-1">OWNER</div>
                  {analysis.owner}
                </div>
              )}
              <div className="flex gap-4 text-xs text-zinc-500">
                <span>Confidence: {analysis?.confidence ?? "—"}</span>
                <span>·</span>
                <span>{analysis?.uncertainty ?? "—"}</span>
              </div>
            </div>
          </details>

          {/* Suggested routes */}
          {analysis?.suggested_routes && analysis.suggested_routes.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs text-zinc-500">SUGGESTED ROUTES</div>
              {analysis.suggested_routes.map((r, i) => (
                <div
                  key={i}
                  className="rounded border border-zinc-700 bg-zinc-800/50 p-3"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <RouteBadge routeId={r.route_id} />
                    <span className="text-xs text-zinc-500">suggested</span>
                  </div>
                  <p className="text-xs text-zinc-300">{r.rationale}</p>
                  {r.evidence_ref && (
                    <p className="font-mono text-xs text-zinc-500 mt-1">{r.evidence_ref}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Manual route — client component */}
      <ManualRoutePanel
        sourceType={type}
        sourceId={decodedId}
        initialManualRoute={record.manual_route}
      />

      {/* Evidence — client component */}
      {evidence && (
        <EvidencePanel
          evidence={evidence}
          hasUsableText={record.has_usable_text}
        />
      )}
    </div>
  )
}
