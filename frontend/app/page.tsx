import Link from "next/link"
import { api } from "@/lib/api"
import { RouteBadge } from "@/components/RouteBadge"
import { ReviewChip, PriorityChip, Tip } from "@/components/Chips"
import { DashboardChart } from "@/components/DashboardChart"
import { recordHref } from "@/lib/utils"
import type { PersonRow } from "@/lib/types"

export const dynamic = "force-dynamic"

function Stat({ label, value, sub, tip, href }: { label: string; value: React.ReactNode; sub?: string; tip: string; href?: string }) {
  const body = (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 h-full hover:border-zinc-700 transition-colors">
      <div className="text-xs text-zinc-400">{label}</div>
      <div className="text-2xl font-semibold text-zinc-100 mt-1">
        {value}
        {sub && <span className="text-sm text-zinc-500 ml-1.5 font-normal">{sub}</span>}
      </div>
      <Tip>{tip}</Tip>
    </div>
  )
  return href ? <Link href={href}>{body}</Link> : body
}

function PeopleTable({ title, rows, kind, note }: { title: string; rows: PersonRow[]; kind: "call" | "meeting"; note: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <div className="text-sm font-medium text-zinc-200">{title}</div>
      <Tip>{note}</Tip>
      <table className="w-full text-xs mt-3">
        <thead>
          <tr className="text-zinc-500 text-left">
            <th className="font-normal py-1">{kind === "call" ? "Rep (rep_name)" : "Organiser (organizer_email)"}</th>
            <th className="font-normal text-right">{kind === "call" ? "Calls" : "Meetings"}</th>
            <th className="font-normal text-right">With text</th>
            {kind === "call" && <th className="font-normal text-right">Connected*</th>}
            <th className="font-normal text-right">Attention</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.person} className="border-t border-zinc-800">
              <td className="py-1.5">
                <Link className="text-zinc-200 hover:text-indigo-300" href={`/?person=${encodeURIComponent(p.person)}`}>
                  {p.person}
                </Link>
              </td>
              <td className="text-right text-zinc-300">
                <Link className="hover:text-indigo-300" href={`/inbox?person=${encodeURIComponent(p.person)}&source_type=${kind}`}>
                  {p.records}
                </Link>
              </td>
              <td className="text-right text-zinc-400">{p.with_text}</td>
              {kind === "call" && (
                <td className="text-right text-zinc-400">
                  {p.connected_source_reported}/{p.connection_known}
                </td>
              )}
              <td className="text-right text-zinc-400">{p.needs_attention || "—"}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td className="py-2 text-zinc-600" colSpan={5}>None in this selection</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: { source_type?: string; person?: string }
}) {
  const params = new URLSearchParams()
  if (searchParams.source_type) params.set("source_type", searchParams.source_type)
  if (searchParams.person) params.set("person", searchParams.person)

  let m
  try {
    m = await api.dashboard(params)
  } catch (e) {
    return (
      <div className="text-red-400 text-sm p-4">
        Could not load the dashboard — is the API running? ({e instanceof Error ? e.message : "error"})
      </div>
    )
  }

  if (m.totals.records === 0 && !searchParams.person && !searchParams.source_type) {
    return (
      <div className="max-w-xl mx-auto mt-16 text-center space-y-3">
        <h1 className="text-xl text-zinc-100">No records imported</h1>
        <p className="text-sm text-zinc-400">Load the supplied deliveries from the Data &amp; replay page.</p>
        <Link href="/data" className="inline-block text-sm text-indigo-300 hover:text-indigo-200">Go to Data &amp; replay →</Link>
      </div>
    )
  }

  const filterQs = params.toString()
  const inboxHref = (extra: string) => `/inbox?${[filterQs, extra].filter(Boolean).join("&")}`
  const cov = m.text_coverage
  const awaiting = m.review_states["awaiting_analysis"] ?? 0
  const human = m.review_states["needs_human_review"] ?? 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">21 August 2026 · Revenue intelligence</h1>
          <p className="text-xs text-zinc-500 mt-1">
            Selected records only (a deliberately chosen sample, not a whole-team day) · Asia/Kolkata · calls by started_at, meetings by starts_at
          </p>
        </div>
        <form className="flex flex-wrap gap-2 items-center" action="/">
          <select name="source_type" defaultValue={searchParams.source_type ?? ""}
            className="bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs rounded h-8 px-2">
            <option value="">Calls + meetings</option>
            <option value="call">Calls only</option>
            <option value="meeting">Meetings only</option>
          </select>
          <select name="person" defaultValue={searchParams.person ?? ""}
            className="bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs rounded h-8 px-2 max-w-[220px]">
            <option value="">Everyone</option>
            <optgroup label="Call reps">
              {m.people.call_reps.map((p) => <option key={p} value={p}>{p}</option>)}
            </optgroup>
            <optgroup label="Meeting organisers">
              {m.people.meeting_organisers.map((p) => <option key={p} value={p}>{p}</option>)}
            </optgroup>
          </select>
          <button className="h-8 px-3 text-xs rounded bg-indigo-600 hover:bg-indigo-500 text-white">Apply</button>
          {(searchParams.person || searchParams.source_type) && (
            <Link href="/" className="text-xs text-zinc-400 hover:text-zinc-200">Clear</Link>
          )}
        </form>
      </div>

      {(searchParams.person || searchParams.source_type) && (
        <div className="text-xs text-indigo-300">
          Filtered: {searchParams.source_type ?? "all types"} · {searchParams.person ?? "everyone"}. All numbers below use this selection as the denominator.
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <Stat label="Selected records" value={m.totals.records}
          sub={`${m.totals.calls} calls · ${m.totals.meetings} meetings`}
          tip="Distinct (source_type, source_id) after revisions; re-imports never add rows." href={inboxHref("")} />
        <Stat label="Usable supplied text" value={`${cov.usable} / ${cov.total}`} sub={cov.pct != null ? `${cov.pct}%` : ""}
          tip={`Calls ${cov.calls.usable}/${cov.calls.total}, meetings ${cov.meetings.usable}/${cov.meetings.total}. Missing text ≠ no conversation.`}
          href={inboxHref("has_usable_text=true")} />
        <Stat label="Needs attention" value={(m.attention.length)}
          tip="Text-backed records that are high priority, need human review, or await analysis of their current revision." href="#attention" />
        <Stat label="Route assignments" value={m.route_assignments} sub={`on ${m.routed_records} records`}
          tip="A record can have several routes, so assignments exceed routed records. Manual route replaces suggestions." href="#routes" />
        <Stat label="Connected calls (source-reported)" value={m.connection.pct != null ? `${m.connection.pct}%` : "—"}
          sub={`${m.connection.connected}/${m.connection.known}`}
          tip={`Upstream is_connected over calls with a non-null value; unknown ${m.connection.unknown}. Not a transcript judgement.`} />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <div className="flex justify-between items-baseline">
            <div className="text-sm font-medium text-zinc-200">Activity by hour (Asia/Kolkata)</div>
            <div className="text-xs text-zinc-500">
              By day: {m.activity_by_day.map((d) => `${d.date} — ${d.total} (${d.calls} calls, ${d.meetings} meetings)`).join("; ") || "—"}
            </div>
          </div>
          <Tip>Every record falls on one date, so the day view is a single bar; the hour view and the person filter give the detail.</Tip>
          <div className="mt-3"><DashboardChart data={m.activity_by_hour} /></div>
        </div>

        <div id="attention" className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <div className="text-sm font-medium text-zinc-200">Needs attention</div>
          <Tip>Highest priority first. Read the evidence behind each on the record page.</Tip>
          <ul className="mt-3 space-y-2.5">
            {m.attention.map((a) => (
              <li key={a.source_id}>
                <Link href={recordHref(a.source_type, a.source_id)} className="group block">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-zinc-300 group-hover:text-indigo-300">{a.record_ref}</span>
                    <PriorityChip priority={a.priority} />
                    <ReviewChip state={a.review_state} />
                  </div>
                  <div className="text-xs text-zinc-400 group-hover:text-zinc-200 leading-snug mt-0.5">
                    {a.headline ?? "Awaiting analysis for the current revision"}
                  </div>
                </Link>
              </li>
            ))}
            {m.attention.length === 0 && <li className="text-xs text-zinc-600">Nothing in this selection.</li>}
          </ul>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <PeopleTable title="Call reps" rows={m.call_reps} kind="call"
          note="Grouped by the source rep_name. *Connected = source-reported is_connected true / known. C06's caller says 'Ravi' while rep_name is Meera — flagged for review." />
        <PeopleTable title="Meeting organisers" rows={m.meeting_organisers} kind="meeting"
          note="Grouped by calendar organizer_email. An organiser is not proof of attendance or a sales role, and is not merged with call reps." />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div id="routes" className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <div className="text-sm font-medium text-zinc-200">Routes</div>
          <Tip>Records per effective route. {m.route_assignments} assignments on {m.routed_records} records; {m.manual_overrides} manual override(s).</Tip>
          <ul className="mt-3 space-y-1.5">
            {m.routes.map((r) => (
              <li key={r.route_id}>
                <Link href={inboxHref(`route_id=${r.route_id}`)} className="flex items-center justify-between hover:bg-zinc-800/60 rounded px-1 py-0.5" title={r.definition}>
                  <RouteBadge routeId={r.route_id} />
                  <span className="text-sm text-zinc-300">{r.records}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <div className="text-sm font-medium text-zinc-200">Intake / review state</div>
          <Tip>Every record has a state, including the ones with no usable text.</Tip>
          <ul className="mt-3 space-y-1.5 text-sm">
            {["needs_human_review", "awaiting_analysis", "manual_override", "suggested", "no_text"].map((s) => (
              <li key={s}>
                <Link href={inboxHref(`review_state=${s}`)} className="flex justify-between hover:bg-zinc-800/60 rounded px-1 py-0.5">
                  <ReviewChip state={s} />
                  <span className="text-zinc-300">{m.review_states[s] ?? 0}</span>
                </Link>
              </li>
            ))}
          </ul>
          {(awaiting > 0 || human > 0) && (
            <p className="text-xs text-amber-400/80 mt-3">
              {awaiting > 0 && `${awaiting} record(s) have new text with no analysis for the current revision. `}
              {human > 0 && `${human} need a human decision.`}
            </p>
          )}
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <div className="text-sm font-medium text-zinc-200">Why text is missing</div>
          <Tip>{cov.total - cov.usable} records have no usable supplied text, so no analysis is generated for them.</Tip>
          <ul className="mt-3 space-y-1.5 text-xs">
            {cov.no_text_reasons.map((r) => (
              <li key={r.reason} className="flex justify-between gap-3">
                <span className="text-zinc-400">{r.reason}</span><span className="text-zinc-300">{r.count}</span>
              </li>
            ))}
          </ul>
          {m.label_conflicts.length > 0 && (
            <div className="mt-4 pt-3 border-t border-zinc-800">
              <div className="text-xs text-zinc-300">Stored label conflicts with transcript</div>
              <div className="flex flex-wrap gap-2 mt-1.5">
                {m.label_conflicts.map((c) => (
                  <Link key={c.source_id} href={recordHref(c.source_type, c.source_id)}
                    className="text-xs font-mono text-rose-300 hover:text-rose-200">
                    {c.record_ref} <span className="text-zinc-500">({c.source_label})</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <details id="definitions" className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3">
        <summary className="cursor-pointer text-sm text-zinc-300">Metric definitions</summary>
        <dl className="mt-3 grid md:grid-cols-2 gap-x-6 gap-y-3 text-xs">
          {m.definitions.map((d) => (
            <div key={d.key}>
              <dt className="text-zinc-200">{d.label}</dt>
              <dd className="text-zinc-400 leading-relaxed">{d.definition}</dd>
            </div>
          ))}
        </dl>
      </details>
    </div>
  )
}
