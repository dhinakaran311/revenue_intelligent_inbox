import Link from "next/link"
import { api } from "@/lib/api"
import { RouteBadge } from "@/components/RouteBadge"
import { FreshnessChip } from "@/components/FreshnessChip"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Button } from "@/components/ui/button"
import { DashboardChart } from "@/components/DashboardChart"

export const dynamic = "force-dynamic"

export default async function DashboardPage() {
  let metrics
  try {
    metrics = await api.dashboard()
  } catch {
    return (
      <div className="text-red-400 text-sm p-4">
        Could not load dashboard — is the backend running on port 8000?
      </div>
    )
  }

  const { text_coverage, activity_by_person, route_summary, analysis_state_counts, definitions } = metrics
  const usablePct = text_coverage.total > 0
    ? Math.round((text_coverage.usable / text_coverage.total) * 100)
    : 0
  const noText = text_coverage.total - text_coverage.usable

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-zinc-100">
          21 Aug 2026 · Revenue Intelligence Review
        </h1>
        <p className="text-xs text-zinc-500 mt-1">
          All times in Asia/Kolkata (UTC+05:30) · Activity date from call started_at / meeting starts_at
        </p>
      </div>

      {/* Stat bar */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-1 pt-4 px-4">
            <CardTitle className="text-xs text-zinc-400 font-normal">Total Records</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="text-3xl font-semibold text-zinc-100">{text_coverage.total}</div>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-1 pt-4 px-4">
            <CardTitle className="text-xs text-zinc-400 font-normal">Calls</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="text-3xl font-semibold text-zinc-100">{activity_by_person.calls_total}</div>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-1 pt-4 px-4">
            <CardTitle className="text-xs text-zinc-400 font-normal">Meetings</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="text-3xl font-semibold text-zinc-100">{activity_by_person.meetings_total}</div>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-1 pt-4 px-4">
            <CardTitle className="text-xs text-zinc-400 font-normal">Usable Text</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="text-3xl font-semibold text-zinc-100">
              {text_coverage.usable}
              <span className="text-base text-zinc-500 ml-1">/ {usablePct}%</span>
            </div>
            <Progress value={usablePct} className="mt-2 h-1" />
          </CardContent>
        </Card>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-1 pt-4 px-4">
            <CardTitle className="text-xs text-zinc-400 font-normal">No Text</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="text-3xl font-semibold text-zinc-500">{noText}</div>
          </CardContent>
        </Card>
      </div>

      {/* Three-column grid */}
      <div className="grid md:grid-cols-3 gap-4">
        {/* Activity by person chart — spans 2 cols */}
        <div className="md:col-span-2">
          <Card className="bg-zinc-900 border-zinc-800 h-full">
            <CardHeader className="px-5 pt-5 pb-2">
              <CardTitle className="text-sm font-medium text-zinc-300">Activity by Person</CardTitle>
            </CardHeader>
            <CardContent className="px-5 pb-5">
              <DashboardChart data={activity_by_person.by_person} />
              <p className="text-xs text-zinc-600 mt-2">
                Calls: rep name. Meetings: organiser email. Fields not combined.
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Right column */}
        <div className="space-y-4">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="px-5 pt-5 pb-2">
              <CardTitle className="text-sm font-medium text-zinc-300">Route Summary</CardTitle>
            </CardHeader>
            <CardContent className="px-5 pb-5 space-y-2">
              {route_summary.map((r) => (
                <Link
                  key={r.route_state}
                  href={`/inbox?route_state=${encodeURIComponent(r.route_state)}`}
                  className="flex items-center justify-between hover:bg-zinc-800/50 rounded px-1 py-0.5 transition-colors"
                >
                  <RouteBadge routeId={r.route_state} />
                  <span className="text-sm text-zinc-300 font-medium">{r.count}</span>
                </Link>
              ))}
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="px-5 pt-5 pb-2">
              <CardTitle className="text-sm font-medium text-zinc-300">Analysis State</CardTitle>
            </CardHeader>
            <CardContent className="px-5 pb-5 space-y-2">
              {analysis_state_counts.map((s) => (
                <div key={s.analysis_state} className="flex items-center justify-between">
                  <FreshnessChip state={s.analysis_state} />
                  <span className="text-sm text-zinc-300 font-medium">{s.count}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Definitions */}
      {definitions && Object.keys(definitions).length > 0 && (
        <details className="rounded-lg border border-zinc-800 bg-zinc-900 px-5 py-4">
          <summary className="cursor-pointer text-sm text-zinc-400 hover:text-zinc-200">
            ℹ️ Metric definitions
          </summary>
          <div className="mt-3 space-y-2 text-xs text-zinc-400">
            {Object.entries(definitions).map(([k, v]) => (
              <div key={k}>
                <span className="font-medium text-zinc-300">{k}:</span> {v}
              </div>
            ))}
          </div>
        </details>
      )}

      {/* CTA row */}
      <div className="flex flex-wrap gap-3">
        <Button asChild variant="outline" className="border-zinc-700 text-zinc-300 hover:text-zinc-100">
          <Link href="/inbox">View Inbox →</Link>
        </Button>
        <Button asChild variant="outline" className="border-zinc-700 text-zinc-300 hover:text-zinc-100">
          <Link href="/brief">Manager Brief →</Link>
        </Button>
        <Button asChild variant="outline" className="border-zinc-700 text-zinc-300 hover:text-zinc-100">
          <Link href="/export">Generate Export →</Link>
        </Button>
      </div>
    </div>
  )
}
