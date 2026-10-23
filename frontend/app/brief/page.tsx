import Link from "next/link"
import { api } from "@/lib/api"
import { recordHref } from "@/lib/utils"
import type { Brief, BriefRef } from "@/lib/types"

export const dynamic = "force-dynamic"

function Ref({ r, brief }: { r: BriefRef; brief: Brief }) {
  const st = brief.records[r.record_ref]
  if (!st) return <span className="font-mono text-xs text-zinc-500">{r.record_ref}</span>
  const turn = r.cite?.match(/^turn (\d+)$/)?.[1]
  const href = recordHref(st.source_type, st.source_id, turn ? `turn-${turn}` : "source")
  const flag = !st.imported
    ? "not imported"
    : st.analysis_state === "pending" || st.analysis_state === "stale"
      ? "awaiting analysis of current revision"
      : st.has_manual_route
        ? "manually re-routed"
        : null
  return (
    <Link href={href} className="inline-flex items-baseline gap-1 text-xs hover:text-indigo-200">
      <span className="font-mono text-indigo-300">{r.record_ref}</span>
      {r.cite && <span className="text-zinc-400">{turn ? `turn ${turn}` : `“${r.cite}”`}</span>}
      {flag && <span className="text-amber-400">({flag})</span>}
    </Link>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wide">{title}</h2>
      {children}
    </section>
  )
}

export default async function BriefPage() {
  let brief: Brief
  try {
    brief = await api.brief()
  } catch {
    return <div className="text-red-400 text-sm p-4">Could not load the brief — is the API running?</div>
  }
  const a = brief.activity
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <header className="border-b border-zinc-800 pb-5">
        <p className="text-[11px] text-zinc-500 tracking-widest">MANAGER BRIEF · PREPARED</p>
        <h1 className="text-2xl font-semibold text-zinc-100 mt-1">21 August 2026</h1>
        <p className="text-sm text-zinc-400">Asia/Kolkata</p>
        <p className="text-xs text-zinc-500 mt-3 leading-relaxed">{brief.basis}</p>
      </header>

      <Section title="Activity (live from current state)">
        <p className="text-sm text-zinc-300 leading-relaxed">
          {a.totals.records} selected records: {a.totals.calls} calls and {a.totals.meetings} meetings.
          Usable supplied text for {a.text_coverage.usable} ({a.text_coverage.calls.usable} calls,{" "}
          {a.text_coverage.meetings.usable} meetings). Source-reported connected calls: {a.connection.connected} of{" "}
          {a.connection.known}.
        </p>
        <p className="text-xs text-zinc-500">
          Call reps: {a.call_reps.map((p) => `${p.person} ${p.records} (${p.with_text} with text)`).join(" · ")}.
          {" "}Meeting organisers: {a.meeting_organisers.length} calendar organisers (not merged with reps; see the{" "}
          <Link href="/?source_type=meeting" className="text-indigo-300">dashboard</Link>).
        </p>
      </Section>

      <Section title="Summary">
        <p className="text-sm text-zinc-200 leading-relaxed">{brief.summary}</p>
      </Section>

      <Section title="Priorities">
        <ol className="space-y-4">
          {brief.priorities.map((p) => (
            <li key={p.rank} className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
              <div className="text-sm font-medium text-zinc-100">{p.rank}. {p.title}</div>
              <p className="text-sm text-zinc-400 mt-1">{p.why}</p>
              <p className="text-sm text-zinc-200 mt-2"><span className="text-zinc-500">Do: </span>{p.action}</p>
              <p className="text-xs text-zinc-500 mt-1">Owner: {p.owner}</p>
              <div className="mt-2 space-y-1">
                {p.refs.map((r, i) => (
                  <div key={i} className="text-xs text-zinc-500">
                    <Ref r={r} brief={brief} />
                    {r.quote && <span className="text-zinc-400"> — “{r.quote}”</span>}
                  </div>
                ))}
              </div>
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Follow-ups with stated next steps">
        <ul className="space-y-2">
          {brief.follow_ups.map((f) => (
            <li key={f.record_ref} className="text-sm">
              <Ref r={{ record_ref: f.record_ref, cite: f.cite }} brief={brief} />
              <div className="text-zinc-300">{f.action} <span className="text-zinc-500">· {f.owner}</span></div>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Coaching">
        <ul className="space-y-3">
          {brief.coaching.map((c) => (
            <li key={c.theme} className="text-sm">
              <div className="text-zinc-100">{c.theme}</div>
              <div className="text-zinc-400">{c.detail}</div>
              <div className="flex flex-wrap gap-3 mt-1">{c.refs.map((r, i) => <Ref key={i} r={r} brief={brief} />)}</div>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Product and vendor signals">
        <ul className="space-y-3">
          {brief.product_signals.map((s) => (
            <li key={s.signal} className="text-sm">
              <div className="text-zinc-100">{s.signal}</div>
              <div className="text-zinc-400">{s.detail}</div>
              <div className="flex flex-wrap gap-3 mt-1">{s.refs.map((r, i) => <Ref key={i} r={r} brief={brief} />)}</div>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Data quality">
        <ul className="space-y-3">
          {brief.data_quality.map((q) => (
            <li key={q.issue} className="text-sm">
              <div className="text-zinc-100">{q.issue}</div>
              <div className="text-zinc-400">{q.detail}</div>
              <div className="flex flex-wrap gap-3 mt-1">{q.refs.map((r, i) => <Ref key={i} r={r} brief={brief} />)}</div>
            </li>
          ))}
        </ul>
      </Section>

      <div className="rounded-lg border border-amber-700/50 bg-amber-950/20 p-4">
        <h3 className="text-amber-300 text-sm font-medium mb-2">What this brief does not establish</h3>
        <ul className="list-disc pl-5 space-y-1 text-sm text-amber-100/80">
          {brief.not_established.map((x) => <li key={x}>{x}</li>)}
        </ul>
      </div>
    </div>
  )
}
