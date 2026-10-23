import { api } from "@/lib/api"
import { RouteBadge } from "@/components/RouteBadge"
import type { RecordRow } from "@/lib/types"
import Link from "next/link"

export const dynamic = "force-dynamic"

function groupByRoute(records: RecordRow[]): Record<string, RecordRow[]> {
  const groups: Record<string, RecordRow[]> = {}
  for (const r of records) {
    const key = r.route_state || "pending"
    if (!groups[key]) groups[key] = []
    groups[key].push(r)
  }
  return groups
}

export default async function BriefPage() {
  let metrics, allRecords
  try {
    ;[metrics, allRecords] = await Promise.all([
      api.dashboard(),
      api.records(),
    ])
  } catch {
    return (
      <div className="text-red-400 text-sm p-4">
        Could not load brief — is the backend running?
      </div>
    )
  }

  const usableRecords = allRecords.filter((r) => r.has_usable_text)
  const routed = usableRecords.filter(
    (r) => r.route_state && r.route_state !== "pending" && r.route_state !== "no_text"
  )
  const grouped = groupByRoute(routed)

  const { text_coverage, activity_by_person } = metrics
  const noTextCount = text_coverage.total - text_coverage.usable

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div className="border-b border-zinc-800 pb-6">
        <p className="text-xs text-zinc-500 mb-1 tracking-widest">REVENUE INTELLIGENCE INBOX</p>
        <h1 className="text-2xl font-semibold text-zinc-100">Manager Brief</h1>
        <p className="text-zinc-400 mt-1">21 August 2026 · Asia/Kolkata</p>
      </div>

      {/* Section 1: Activity Scope */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-zinc-300">Activity Scope</h2>
        <p className="text-sm text-zinc-400 leading-relaxed">
          {text_coverage.total} records selected ({activity_by_person.calls_total} calls,{" "}
          {activity_by_person.meetings_total} meetings). All activity on 21 August 2026 in
          Asia/Kolkata. Text coverage: {text_coverage.usable} of {text_coverage.total} records
          have usable supplied text.
        </p>
      </section>

      {/* Section 2: Priorities */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold text-zinc-300">Priorities This Period</h2>
        {Object.entries(grouped).length === 0 ? (
          <p className="text-sm text-zinc-500">No routed records with usable text.</p>
        ) : (
          Object.entries(grouped).map(([routeId, recs]) => (
            <div key={routeId} className="space-y-2">
              <RouteBadge routeId={routeId} />
              <ul className="space-y-1 pl-2">
                {recs.map((r) => (
                  <li key={r.source_id} className="flex items-start gap-2 text-sm">
                    <Link
                      href={`/records/${r.source_type}/${encodeURIComponent(r.source_id)}`}
                      className="text-zinc-300 hover:text-indigo-400 font-mono text-xs"
                    >
                      {r.record_ref ?? r.source_id}
                    </Link>
                    <span className="text-zinc-500 text-xs">
                      {r.person_name ?? "—"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))
        )}
      </section>

      {/* Section 3: Coverage Limitation — MANDATORY, cannot be hidden */}
      <div className="rounded-lg border border-amber-800/50 bg-amber-950/20 p-5">
        <h3 className="text-amber-300 font-medium mb-2">⚠ Coverage Limitation</h3>
        <p className="text-sm text-amber-400/80 leading-relaxed">
          {noTextCount} of {text_coverage.total} records have no usable supplied text. No analysis
          has been generated for these records. Counts reflect selected records only; no inference
          about unrecorded activity is made.
        </p>
      </div>
    </div>
  )
}
