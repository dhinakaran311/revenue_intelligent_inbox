"use client"
import { useRouter, useSearchParams } from "next/navigation"
import { useCallback, useState } from "react"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface InboxFiltersProps {
  sourceType?: string
  hasUsableText?: string
  routeState?: string
  personName?: string
}

export function InboxFilters({
  sourceType,
  hasUsableText,
  routeState,
  personName,
}: InboxFiltersProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [personInput, setPersonInput] = useState(personName ?? "")

  const updateParam = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString())
      if (value && value !== "all") {
        params.set(key, value)
      } else {
        params.delete(key)
      }
      router.push(`/inbox?${params.toString()}`)
    },
    [router, searchParams]
  )

  // Debounced person search
  let debounceTimer: ReturnType<typeof setTimeout>
  const handlePersonChange = (val: string) => {
    setPersonInput(val)
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => updateParam("person_name", val), 300)
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Select
        value={sourceType ?? "all"}
        onValueChange={(v) => updateParam("source_type", v)}
      >
        <SelectTrigger className="w-36 bg-zinc-900 border-zinc-700 text-zinc-300 text-xs h-8">
          <SelectValue placeholder="All types" />
        </SelectTrigger>
        <SelectContent className="bg-zinc-900 border-zinc-700">
          <SelectItem value="all" className="text-zinc-300 text-xs">All Types</SelectItem>
          <SelectItem value="call" className="text-zinc-300 text-xs">📞 Calls</SelectItem>
          <SelectItem value="meeting" className="text-zinc-300 text-xs">🤝 Meetings</SelectItem>
        </SelectContent>
      </Select>

      <Select
        value={hasUsableText ?? "all"}
        onValueChange={(v) => updateParam("has_usable_text", v)}
      >
        <SelectTrigger className="w-36 bg-zinc-900 border-zinc-700 text-zinc-300 text-xs h-8">
          <SelectValue placeholder="All text" />
        </SelectTrigger>
        <SelectContent className="bg-zinc-900 border-zinc-700">
          <SelectItem value="all" className="text-zinc-300 text-xs">All Text</SelectItem>
          <SelectItem value="true" className="text-zinc-300 text-xs">Has Text</SelectItem>
          <SelectItem value="false" className="text-zinc-300 text-xs">No Text</SelectItem>
        </SelectContent>
      </Select>

      <Select
        value={routeState ?? "all"}
        onValueChange={(v) => updateParam("route_state", v)}
      >
        <SelectTrigger className="w-44 bg-zinc-900 border-zinc-700 text-zinc-300 text-xs h-8">
          <SelectValue placeholder="All routes" />
        </SelectTrigger>
        <SelectContent className="bg-zinc-900 border-zinc-700">
          <SelectItem value="all" className="text-zinc-300 text-xs">All Routes</SelectItem>
          <SelectItem value="deal_next_step" className="text-zinc-300 text-xs">Deal Next Step</SelectItem>
          <SelectItem value="customer_follow_up" className="text-zinc-300 text-xs">Customer Follow-Up</SelectItem>
          <SelectItem value="sales_coaching" className="text-zinc-300 text-xs">Sales Coaching</SelectItem>
          <SelectItem value="internal_vendor_action" className="text-zinc-300 text-xs">Internal/Vendor</SelectItem>
          <SelectItem value="human_review" className="text-zinc-300 text-xs">Human Review</SelectItem>
          <SelectItem value="pending" className="text-zinc-300 text-xs">Pending Review</SelectItem>
          <SelectItem value="no_text" className="text-zinc-300 text-xs">No Text</SelectItem>
        </SelectContent>
      </Select>

      <Input
        placeholder="Search person…"
        value={personInput}
        onChange={(e) => handlePersonChange(e.target.value)}
        className="w-44 bg-zinc-900 border-zinc-700 text-zinc-300 placeholder-zinc-600 text-xs h-8"
      />
    </div>
  )
}
