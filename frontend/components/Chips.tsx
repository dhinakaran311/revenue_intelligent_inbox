import { cn, PRIORITY_COLOURS, REVIEW_COLOURS, REVIEW_LABELS } from "@/lib/utils"

export function ReviewChip({ state }: { state: string }) {
  return (
    <span className={cn("text-xs font-medium whitespace-nowrap", REVIEW_COLOURS[state] ?? "text-zinc-400")}>
      {REVIEW_LABELS[state] ?? state}
    </span>
  )
}

export function PriorityChip({ priority }: { priority: string | null | undefined }) {
  if (!priority) return null
  return (
    <span className={cn("text-[10px] uppercase tracking-wide border rounded px-1.5 py-0.5", PRIORITY_COLOURS[priority])}>
      {priority}
    </span>
  )
}

export function SourceChip({ type }: { type: string }) {
  return (
    <span
      className={cn(
        "text-[10px] uppercase tracking-wide rounded px-1.5 py-0.5 border",
        type === "call" ? "text-indigo-300 border-indigo-500/30" : "text-amber-300 border-amber-500/30"
      )}
    >
      {type}
    </span>
  )
}

export function Tip({ children }: { children: React.ReactNode }) {
  return <p className="text-[11px] leading-snug text-zinc-500 mt-1.5">{children}</p>
}
