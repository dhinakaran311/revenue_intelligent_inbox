import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const ROUTE_LABELS: Record<string, string> = {
  deal_next_step: "Deal / partner next step",
  customer_follow_up: "Customer follow-up",
  sales_coaching: "Sales coaching",
  internal_vendor_action: "Internal / product / vendor",
  human_review: "Human review",
  log_only: "Log only",
}

export const ROUTE_COLOURS: Record<string, string> = {
  deal_next_step: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  customer_follow_up: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  sales_coaching: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  internal_vendor_action: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  human_review: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  log_only: "bg-zinc-500/15 text-zinc-400 border-zinc-600",
}

export const REVIEW_LABELS: Record<string, string> = {
  no_text: "No usable text",
  awaiting_analysis: "Awaiting analysis",
  needs_human_review: "Needs human review",
  manual_override: "Manual route",
  suggested: "Suggested route",
}

export const REVIEW_COLOURS: Record<string, string> = {
  no_text: "text-zinc-500",
  awaiting_analysis: "text-amber-400",
  needs_human_review: "text-rose-400",
  manual_override: "text-indigo-300",
  suggested: "text-emerald-400",
}

export const PRIORITY_COLOURS: Record<string, string> = {
  high: "text-rose-300 border-rose-500/40",
  medium: "text-amber-300 border-amber-500/40",
  low: "text-zinc-400 border-zinc-600",
}

export function recordHref(type: string, id: string, anchor?: string) {
  return `/records/${type}/${encodeURIComponent(id)}${anchor ? `#${anchor}` : ""}`
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}
