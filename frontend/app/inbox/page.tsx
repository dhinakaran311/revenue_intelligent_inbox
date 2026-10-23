import Link from "next/link"
import { api } from "@/lib/api"
import { RouteBadge } from "@/components/RouteBadge"
import { SourceTypeBadge } from "@/components/SourceTypeBadge"
import { PersonRoleChip } from "@/components/PersonRoleChip"
import { FreshnessChip } from "@/components/FreshnessChip"
import { formatDate } from "@/lib/utils"
import { InboxFilters } from "@/components/InboxFilters"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export const dynamic = "force-dynamic"

interface SearchParams {
  source_type?: string
  has_usable_text?: string
  route_state?: string
  person_name?: string
}

export default async function InboxPage({
  searchParams,
}: {
  searchParams: SearchParams
}) {
  const params = new URLSearchParams()
  if (searchParams.source_type) params.set("source_type", searchParams.source_type)
  if (searchParams.has_usable_text) params.set("has_usable_text", searchParams.has_usable_text)
  if (searchParams.route_state) params.set("route_state", searchParams.route_state)
  if (searchParams.person_name) params.set("person_name", searchParams.person_name)

  let records
  try {
    records = await api.records(params)
  } catch {
    return (
      <div className="text-red-400 text-sm p-4">
        Could not load records — is the backend running?
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-100">Inbox</h1>
        <span className="text-xs text-zinc-500">
          Showing {records.length} of 44 records
        </span>
      </div>

      <InboxFilters
        sourceType={searchParams.source_type}
        hasUsableText={searchParams.has_usable_text}
        routeState={searchParams.route_state}
        personName={searchParams.person_name}
      />

      <div className="rounded-lg border border-zinc-800 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-500 font-medium text-xs">Ref</TableHead>
              <TableHead className="text-zinc-500 font-medium text-xs">Type</TableHead>
              <TableHead className="text-zinc-500 font-medium text-xs">Person</TableHead>
              <TableHead className="text-zinc-500 font-medium text-xs">Date</TableHead>
              <TableHead className="text-zinc-500 font-medium text-xs">Text</TableHead>
              <TableHead className="text-zinc-500 font-medium text-xs">Route</TableHead>
              <TableHead className="text-zinc-500 font-medium text-xs">Analysis</TableHead>
              <TableHead className="text-zinc-500 font-medium text-xs w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {records.map((record) => (
              <TableRow
                key={`${record.source_type}/${record.source_id}`}
                className={[
                  "border-zinc-800 transition-colors",
                  record.has_manual_route ? "border-l-2 border-l-indigo-500" : "",
                  !record.has_usable_text ? "opacity-60" : "",
                ].join(" ")}
              >
                <TableCell className="py-2.5">
                  <span className="font-mono text-xs text-zinc-400">
                    {record.record_ref ?? record.source_id}
                  </span>
                </TableCell>
                <TableCell className="py-2.5">
                  <SourceTypeBadge type={record.source_type} />
                </TableCell>
                <TableCell className="py-2.5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs text-zinc-300">{record.person_name ?? "—"}</span>
                    <PersonRoleChip role={record.person_role} />
                  </div>
                </TableCell>
                <TableCell className="py-2.5 text-xs text-zinc-400">
                  {formatDate(record.activity_date)}
                </TableCell>
                <TableCell className="py-2.5">
                  {record.has_usable_text ? (
                    <span className="text-xs text-green-400">✓ Usable</span>
                  ) : (
                    <span className="text-xs text-zinc-600">— No text</span>
                  )}
                </TableCell>
                <TableCell className="py-2.5">
                  {record.route_state && record.route_state !== "pending" ? (
                    <RouteBadge routeId={record.route_state} />
                  ) : (
                    <span className="text-xs text-zinc-600">{record.route_state ?? "—"}</span>
                  )}
                </TableCell>
                <TableCell className="py-2.5">
                  {record.analysis_source ? (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                      {record.analysis_source.toUpperCase()}
                    </span>
                  ) : (
                    <FreshnessChip state={record.analysis_state} />
                  )}
                </TableCell>
                <TableCell className="py-2.5">
                  <Button
                    asChild
                    variant="ghost"
                    size="sm"
                    className="text-xs text-zinc-400 hover:text-zinc-100 h-6 px-2"
                  >
                    <Link
                      href={`/records/${record.source_type}/${encodeURIComponent(record.source_id)}`}
                    >
                      View
                    </Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
