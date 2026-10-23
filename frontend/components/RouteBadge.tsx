import { cn, ROUTE_COLOURS, ROUTE_LABELS } from "@/lib/utils"

export function RouteBadge({ routeId }: { routeId: string }) {
  return (
    <span
      className={cn(
        "px-2 py-0.5 rounded text-xs font-medium border",
        ROUTE_COLOURS[routeId] ?? "bg-zinc-700 text-zinc-300 border-zinc-600"
      )}
    >
      {ROUTE_LABELS[routeId] ?? routeId}
    </span>
  )
}
