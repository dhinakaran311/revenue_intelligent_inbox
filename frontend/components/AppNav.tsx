"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"

const NAV_LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/inbox", label: "Inbox" },
  { href: "/brief", label: "Brief" },
  { href: "/export", label: "Export" },
  { href: "/data", label: "Data & replay" },
]

export function AppNav() {
  const pathname = usePathname()

  return (
    <nav className="sticky top-0 z-50 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between h-[52px]">
        <span className="font-medium text-zinc-100 text-sm tracking-tight">
          Revenue Intelligence Inbox
        </span>
        <div className="flex items-center gap-1">
          {NAV_LINKS.map((link) => {
            const isActive =
              link.href === "/"
                ? pathname === "/"
                : pathname.startsWith(link.href)
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`px-3 py-1.5 text-sm rounded-sm transition-colors ${
                  isActive
                    ? "text-indigo-400 border-b border-indigo-400"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {link.label}
              </Link>
            )
          })}
        </div>
      </div>
    </nav>
  )
}
