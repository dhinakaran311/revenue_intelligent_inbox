import type { Metadata } from "next"
import { GeistSans } from "geist/font/sans"
import { GeistMono } from "geist/font/mono"
import "./globals.css"
import { AppNav } from "@/components/AppNav"

export const metadata: Metadata = {
  title: "Revenue Intelligence Inbox",
  description: "Manager review tool — 21 Aug 2026",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-screen bg-zinc-950 font-sans antialiased">
        <AppNav />
        <main className="px-6 py-6 max-w-7xl mx-auto">{children}</main>
      </body>
    </html>
  )
}
