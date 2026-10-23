export function PersonRoleChip({ role }: { role: string | null | undefined }) {
  if (!role) return null
  return (
    <span className="text-xs text-zinc-400 font-medium tracking-wider uppercase">
      {role === "REP" ? "Rep" : role === "ORG" ? "Org" : role}
    </span>
  )
}
