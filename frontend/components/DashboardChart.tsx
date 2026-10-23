"use client"
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts"

export function DashboardChart({
  data,
}: {
  data: Array<{ hour: string; calls: number; meetings: number }>
}) {
  if (!data || data.length === 0) {
    return <div className="text-xs text-zinc-500 py-4">No activity for this selection</div>
  }
  const chartData = data.map((d) => ({ name: d.hour, Calls: d.calls, Meetings: d.meetings }))
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={chartData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
        <XAxis dataKey="name" tick={{ fill: "#a1a1aa", fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis allowDecimals={false} tick={{ fill: "#71717a", fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip
          cursor={{ fill: "#27272a" }}
          contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 6, fontSize: 12, color: "#e4e4e7" }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: "#a1a1aa" }} />
        <Bar dataKey="Calls" stackId="a" fill="#6366f1" />
        <Bar dataKey="Meetings" stackId="a" fill="#f59e0b" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
