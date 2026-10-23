import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const ROUTE_LABELS: Record<string, string> = {
  deal_next_step: "Deal Next Step",
  customer_follow_up: "Customer Follow-Up",
  sales_coaching: "Sales Coaching",
  internal_vendor_action: "Internal / Vendor Action",
  human_review: "Human Review",
}

export const ROUTE_COLOURS: Record<string, string> = {
  deal_next_step:
    "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
  customer_follow_up:
    "bg-amber-500/20 text-amber-300 border-amber-500/30",
  sales_coaching:
    "bg-green-500/20 text-green-300 border-green-500/30",
  internal_vendor_action:
    "bg-blue-500/20 text-blue-300 border-blue-500/30",
  human_review: "bg-red-500/20 text-red-300 border-red-500/30",
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
