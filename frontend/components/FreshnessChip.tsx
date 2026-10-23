const STATE_COLOURS: Record<string, string> = {
  current: "text-green-400",
  stale: "text-amber-400",
  pending: "text-zinc-400",
  no_text: "text-zinc-600",
}

export function FreshnessChip({ state }: { state: string | null | undefined }) {
  const s = state ?? "pending"
  return (
    <span className={`text-xs font-medium ${STATE_COLOURS[s] ?? "text-zinc-400"}`}>
      {s.replace("_", " ")}
    </span>
  )
}
