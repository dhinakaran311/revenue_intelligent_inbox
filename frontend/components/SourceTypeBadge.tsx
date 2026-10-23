export function SourceTypeBadge({ type }: { type: string }) {
  if (type === "call") {
    return <span className="text-xs text-zinc-300">📞 Call</span>
  }
  if (type === "meeting") {
    return <span className="text-xs text-zinc-300">🤝 Meeting</span>
  }
  return <span className="text-xs text-zinc-400">{type}</span>
}
