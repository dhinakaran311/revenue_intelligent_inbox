import Link from "next/link"
import { api } from "@/lib/api"
import { RouteBadge } from "@/components/RouteBadge"
import { ReviewChip, PriorityChip, SourceChip } from "@/components/Chips"
import { ManualRoutePanel } from "@/components/ManualRoutePanel"
import { AnalysisActions } from "@/components/AnalysisActions"
import { formatTime } from "@/lib/utils"
import type { Analysis, Evidence } from "@/lib/types"

export const dynamic = "force-dynamic"

function highlightCall(text: string, quotes: Array<{ id: string; quote: string }>) {
  // Split the transcript into plain and cited segments (non-overlapping, in order).
  const hits = quotes
    .map((q) => ({ ...q, at: text.indexOf(q.quote) }))
    .filter((q) => q.at >= 0)
    .sort((a, b) => a.at - b.at)
  const parts: React.ReactNode[] = []
  let pos = 0
  for (const h of hits) {
    if (h.at < pos) continue
    parts.push(text.slice(pos, h.at))
    parts.push(
      <mark key={h.id} id={`ev-${h.id}`} className="bg-amber-400/20 text-amber-100 rounded px-0.5 scroll-mt-24">
        {h.quote}
        <sup className="text-amber-300 ml-0.5">{h.id}</sup>
      </mark>
    )
    pos = h.at + h.quote.length
  }
  parts.push(text.slice(pos))
  return parts
}

function SourceText({ evidence }: { evidence: Evidence }) {
  if (!evidence.has_usable_text) return null
  const cited = new Map<number, string[]>()
  for (const e of evidence.evidence) {
    if (e.turn) cited.set(e.turn, [...(cited.get(e.turn) ?? []), e.id])
  }
  return (
    <div id="source" className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <div className="text-sm font-medium text-zinc-200">Supplied conversation text</div>
      <p className="text-[11px] text-zinc-500 mt-1">
        Adapted, abridged source text. {evidence.transcript !== null
          ? "Call text has no reliable turns or timings; cited passages are highlighted as exact quotes."
          : "Turn numbers are 1-based positions in the supplied turns array (timecodes are not IDs). Cited turns are highlighted."}
      </p>
      {evidence.transcript !== null ? (
        <p className="mt-3 text-sm leading-relaxed text-zinc-300 whitespace-pre-wrap">
          {highlightCall(evidence.transcript ?? "", evidence.evidence)}
        </p>
      ) : (
        <ol className="mt-3 space-y-2">
          {evidence.turns.map((t) => {
            const ids = cited.get(t.turn_number)
            return (
              <li key={t.turn_number} id={`turn-${t.turn_number}`}
                className={`scroll-mt-24 rounded px-2 py-1.5 text-sm ${ids ? "bg-amber-400/10 border-l-2 border-amber-400" : ""}`}>
                <div className="text-[11px] text-zinc-500">
                  Turn {t.turn_number} · {t.speaker} · {t.timecode}
                  {ids && <span className="text-amber-300 ml-2">cited {ids.join(", ")}</span>}
                </div>
                <div className="text-zinc-300 leading-relaxed">{t.text}</div>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}

function AnalysisBlock({ a, refText }: { a: Analysis; refText: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-300 border border-sky-500/30 uppercase tracking-wide">
          {a.analysis_source} analysis
        </span>
        <span className="text-zinc-500">of revision {a.source_revision} · confidence {a.confidence}</span>
        <PriorityChip priority={a.priority} />
      </div>
      {a.headline && <h2 className="text-base font-medium text-zinc-100">{a.headline}</h2>}
      <p className="text-sm text-zinc-300 leading-relaxed">{a.concise_output}</p>

      <div className="grid md:grid-cols-2 gap-4 text-sm">
        <div>
          <div className="text-[11px] text-zinc-500 mb-1">WHAT THE EVIDENCE ESTABLISHES</div>
          <p className="text-zinc-300">{a.what_established}</p>
        </div>
        <div>
          <div className="text-[11px] text-zinc-500 mb-1">WHAT IT DOES NOT ESTABLISH</div>
          <p className="text-zinc-300">{a.what_not_established}</p>
        </div>
        <div>
          <div className="text-[11px] text-zinc-500 mb-1">NEXT ACTION</div>
          <p className="text-zinc-200">{a.next_action}</p>
        </div>
        <div>
          <div className="text-[11px] text-zinc-500 mb-1">OWNER</div>
          <p className="text-zinc-300">{a.owner ?? "Not stated in the source"}</p>
          <div className="text-[11px] text-zinc-500 mt-2">UNCERTAINTY</div>
          <p className="text-zinc-400 text-xs">{a.uncertainty}</p>
        </div>
      </div>

      {a.label_check && (
        <div className={`text-xs rounded px-3 py-2 border ${a.label_agrees === false ? "border-rose-500/40 text-rose-200 bg-rose-500/10" : "border-zinc-700 text-zinc-400"}`}>
          <span className="font-medium">Source label check: </span>{a.label_check}
        </div>
      )}

      <div>
        <div className="text-[11px] text-zinc-500 mb-2">SUGGESTED ROUTES AND THEIR OUTPUTS</div>
        <div className="space-y-2">
          {a.suggested_routes.map((r) => (
            <div key={r.route_id} className="rounded border border-zinc-700 bg-zinc-800/40 p-3">
              <div className="flex items-center gap-2 flex-wrap">
                <RouteBadge routeId={r.route_id} />
                <span className="text-[10px] text-zinc-500 uppercase">suggested</span>
                <PriorityChip priority={r.priority} />
                <span className="text-[11px] text-zinc-500 ml-auto">{r.evidence_ref}</span>
              </div>
              {r.output && <p className="text-sm text-zinc-200 mt-2 leading-relaxed">{r.output}</p>}
              <p className="text-xs text-zinc-500 mt-1.5">Why: {r.rationale}</p>
              {r.owner && <p className="text-xs text-zinc-500">Owner: {r.owner}</p>}
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="text-[11px] text-zinc-500 mb-2">EVIDENCE (click to jump to the passage)</div>
        <ul className="space-y-1.5">
          {a.evidence.map((e) => (
            <li key={e.id} className="text-xs">
              <a href={e.turn ? `#turn-${e.turn}` : `#ev-${e.id}`} className="group">
                <span className="text-amber-300 font-mono mr-1.5">{e.id}</span>
                <span className="text-zinc-500 mr-1.5">{e.turn ? `${refText} turn ${e.turn}` : `${refText} quote`}</span>
                <span className="text-zinc-200 group-hover:text-white">“{e.quote}”</span>
                <span className="text-zinc-500"> — {e.supports}</span>
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default async function RecordDetailPage({ params }: { params: { type: string; id: string } }) {
  const type = params.type
  const id = decodeURIComponent(params.id)

  let record, evidence
  try {
    ;[record, evidence] = await Promise.all([api.recordDetail(type, id), api.recordEvidence(type, id)])
  } catch (e) {
    return <div className="text-red-400 text-sm p-4">Could not load record: {e instanceof Error ? e.message : ""}</div>
  }
  const p = (record.source_payload ?? {}) as Record<string, unknown>
  const meta: Array<[string, unknown]> =
    type === "call"
      ? [["rep_name", p.rep_name], ["direction", p.direction], ["duration_seconds", p.duration_seconds],
         ["is_connected (source)", p.is_connected], ["is_conversation (source)", p.is_conversation],
         ["observed_outcome (source)", p.observed_outcome], ["is_campaign_call", p.is_campaign_call]]
      : [["title", p.title], ["organizer_email", p.organizer_email], ["attendee_count (source)", p.attendee_count],
         ["recording_status", p.recording_status], ["recording_detail", p.recording_detail],
         ["duration_seconds (source)", p.duration_seconds], ["has_transcript flag", p.has_transcript]]

  const refText = record.record_ref ?? record.source_id.slice(0, 8)

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <Link href="/inbox" className="text-xs text-zinc-500 hover:text-zinc-300">← Inbox</Link>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <SourceChip type={record.source_type} />
          <span className="text-lg font-semibold text-zinc-100">{refText}</span>
          {record.title && <span className="text-zinc-300">{record.title}</span>}
          <span className="ml-auto"><ReviewChip state={record.review_state} /></span>
        </div>
        <div className="text-xs text-zinc-400 mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
          <span>{formatTime(record.activity_at)} IST</span>
          <span>{record.source_type === "call" ? "Rep" : "Organiser"}: {record.person_name ?? "—"}</span>
          <span>Applied source revision {record.revision}</span>
          <span>Analysis: {record.analysis_state}</span>
          <span className="font-mono text-zinc-600">{record.source_type}/{record.source_id}</span>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-2">
          {record.effective_route_ids.map((r) => <RouteBadge key={r} routeId={r} />)}
          {record.has_manual_route && <span className="text-[11px] text-indigo-300">manual</span>}
        </div>
      </div>

      {!record.has_usable_text && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-4">
          <div className="font-medium text-zinc-200">No usable supplied text — analysis unavailable</div>
          <p className="text-sm text-zinc-400 mt-1">{record.text_status}</p>
          <p className="text-xs text-zinc-500 mt-1">
            Intake only. Nothing is concluded about this conversation; a missing transcript does not prove it did not happen.
          </p>
        </div>
      )}

      {record.has_usable_text && !record.current_analysis && (
        <div className="rounded-lg border border-amber-600/50 bg-amber-950/30 p-4 space-y-2">
          <div className="font-medium text-amber-200">
            Awaiting analysis for revision {record.revision}
          </div>
          <p className="text-sm text-amber-100/80">
            The source text for this record changed (or arrived late). No analysis reflects revision {record.revision} yet, so
            none is shown as current.{record.stale_analysis ? ` An analysis of revision ${record.stale_analysis.source_revision} exists as history only.` : ""}
            {record.has_manual_route ? " The manager's manual route stays in effect." : ""}
          </p>
          <AnalysisActions sourceType={record.source_type} sourceId={record.source_id} />
        </div>
      )}

      <div className="grid lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 space-y-4">
          {record.current_analysis && <AnalysisBlock a={record.current_analysis} refText={refText} />}
          <SourceText evidence={evidence} />
        </div>
        <div className="lg:col-span-2 space-y-4">
          <ManualRoutePanel
            sourceType={record.source_type}
            sourceId={record.source_id}
            manualRoute={record.manual_route}
            suggested={record.suggested_route_ids}
            history={record.manual_route_history}
          />
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
            <div className="text-sm font-medium text-zinc-200">Source metadata</div>
            <p className="text-[11px] text-zinc-500 mt-1">Stored upstream values, shown as reported, not as verified facts.</p>
            <dl className="mt-2 text-xs space-y-1">
              {meta.map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3">
                  <dt className="text-zinc-500">{k}</dt>
                  <dd className="text-zinc-300 text-right break-all">{v === null || v === undefined ? "null" : String(v)}</dd>
                </div>
              ))}
            </dl>
            <details className="mt-3">
              <summary className="cursor-pointer text-[11px] text-zinc-500">Raw source payload</summary>
              <pre className="mt-2 text-[10px] text-zinc-400 overflow-x-auto max-h-80">
                {JSON.stringify({ ...p, transcript: p.transcript ? "(shown above)" : p.transcript }, null, 2)}
              </pre>
            </details>
          </div>
        </div>
      </div>
    </div>
  )
}
