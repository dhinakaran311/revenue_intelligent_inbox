import Link from "next/link"
import { api } from "@/lib/api"
import { RouteBadge } from "@/components/RouteBadge"
import { ReviewChip, PriorityChip, SourceChip } from "@/components/Chips"
import { ROUTE_LABELS, REVIEW_LABELS, formatTime, recordHref } from "@/lib/utils"

export const dynamic = "force-dynamic"

type SP = {
  source_type?: string
  has_usable_text?: string
  route_id?: string
  review_state?: string
  person?: string
}

export default async function InboxPage({ searchParams }: { searchParams: SP }) {
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(searchParams)) if (v) params.set(k, v)

  let records, all
  try {
    ;[records, all] = await Promise.all([api.records(params), api.records()])
  } catch {
    return <div className="text-red-400 text-sm p-4">Could not load records — is the API running?</div>
  }
  const people = Array.from(new Set(all.map((r) => r.person_name).filter(Boolean))) as string[]
  const sel = "bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs rounded h-8 px-2"

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-semibold text-zinc-100">Inbox</h1>
        <span className="text-xs text-zinc-500">
          Showing {records.length} of {all.length} records · newest first (Asia/Kolkata)
        </span>
      </div>

      <form action="/inbox" className="flex flex-wrap gap-2 items-center">
        <select name="source_type" defaultValue={searchParams.source_type ?? ""} className={sel}>
          <option value="">All types</option>
          <option value="call">Calls</option>
          <option value="meeting">Meetings</option>
        </select>
        <select name="review_state" defaultValue={searchParams.review_state ?? ""} className={sel}>
          <option value="">Any review state</option>
          {Object.entries(REVIEW_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select name="route_id" defaultValue={searchParams.route_id ?? ""} className={sel}>
          <option value="">Any route</option>
          {Object.entries(ROUTE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select name="has_usable_text" defaultValue={searchParams.has_usable_text ?? ""} className={sel}>
          <option value="">Text: any</option>
          <option value="true">Usable text</option>
          <option value="false">No usable text</option>
        </select>
        <select name="person" defaultValue={searchParams.person ?? ""} className={`${sel} max-w-[200px]`}>
          <option value="">Anyone</option>
          {people.sort().map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <button className="h-8 px-3 text-xs rounded bg-indigo-600 hover:bg-indigo-500 text-white">Filter</button>
        {params.toString() && <Link href="/inbox" className="text-xs text-zinc-400 hover:text-zinc-200">Clear</Link>}
      </form>

      <div className="rounded-lg border border-zinc-800 overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-zinc-900 text-zinc-500 text-left">
            <tr>
              <th className="font-normal px-3 py-2">Ref</th>
              <th className="font-normal px-3 py-2">Time</th>
              <th className="font-normal px-3 py-2">Person</th>
              <th className="font-normal px-3 py-2 w-[38%]">What matters</th>
              <th className="font-normal px-3 py-2">Routes</th>
              <th className="font-normal px-3 py-2">Review state</th>
            </tr>
          </thead>
          <tbody>
            {records.map((r) => (
              <tr key={`${r.source_type}/${r.source_id}`}
                className={`border-t border-zinc-800 hover:bg-zinc-900/70 ${r.has_usable_text ? "" : "opacity-60"}`}>
                <td className="px-3 py-2 align-top">
                  <Link href={recordHref(r.source_type, r.source_id)} className="font-mono text-zinc-200 hover:text-indigo-300">
                    {r.record_ref ?? r.source_id.slice(0, 8)}
                  </Link>
                  <div className="mt-1 flex gap-1 items-center">
                    <SourceChip type={r.source_type} />
                    {r.revision > 1 && <span className="text-[10px] text-amber-300">rev {r.revision}</span>}
                  </div>
                </td>
                <td className="px-3 py-2 align-top text-zinc-400 whitespace-nowrap">{formatTime(r.activity_at)}</td>
                <td className="px-3 py-2 align-top">
                  <div className="text-zinc-300">{r.person_name ?? "—"}</div>
                  <div className="text-[10px] text-zinc-500">{r.source_type === "call" ? "rep" : "organiser"}</div>
                </td>
                <td className="px-3 py-2 align-top">
                  <Link href={recordHref(r.source_type, r.source_id)} className="hover:text-zinc-100">
                    {r.headline ? (
                      <span className="text-zinc-200">{r.headline}</span>
                    ) : (
                      <span className="text-zinc-500">{r.title ? `${r.title} — ` : ""}{r.text_status}</span>
                    )}
                  </Link>
                  <div className="mt-1 flex gap-2 items-center">
                    <PriorityChip priority={r.priority} />
                    {r.label_agrees === false && <span className="text-[10px] text-rose-300">label conflict</span>}
                    {r.source_label && <span className="text-[10px] text-zinc-600">source: {r.source_label}</span>}
                  </div>
                </td>
                <td className="px-3 py-2 align-top">
                  <div className="flex flex-wrap gap-1">
                    {r.effective_route_ids.map((id) => <RouteBadge key={id} routeId={id} />)}
                    {r.effective_route_ids.length === 0 && <span className="text-zinc-600">—</span>}
                  </div>
                  {r.has_manual_route && <div className="text-[10px] text-indigo-300 mt-1">manual (overrides suggestion)</div>}
                </td>
                <td className="px-3 py-2 align-top">
                  <ReviewChip state={r.review_state} />
                  {r.has_usable_text && (
                    <div className="text-[10px] text-zinc-500 mt-0.5">
                      analysis {r.analysis_state}{r.analysis_source ? ` · ${r.analysis_source}` : ""}
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {records.length === 0 && (
              <tr><td colSpan={6} className="px-3 py-6 text-center text-zinc-500">No records match these filters.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
