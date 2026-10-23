"use client"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"

interface PersonActivity {
  person_name: string
  person_role: string
  calls: number
  meetings: number
}

export function DashboardChart({ data }: { data: PersonActivity[] }) {
  if (!data || data.length === 0) {
    return <div className="text-xs text-zinc-500 py-4">No activity data</div>
  }

  const chartData = data.map((d) => ({
    name: d.person_name,
    Calls: d.calls,
    Meetings: d.meetings,
  }))

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{top: 0, right: 8, left: 8, bottom: 0}}
      >
        <XAxis type="number" tick={{fill: "#71717a", fontSize: 11}} axisLine={false} tickLine={false} />
        <YAxis
          type="category"
          dataKey="name"
          tick={{fill: "#a1a1aa", fontSize: 11}}
          axisLine={false}
          tickLine={false}
          width={120}
        />
        <Tooltip
          contentStyle={{background: "#18181b",
            border: "1px solid #3f3f46",
            borderRadius: "6px",
            fontSize: 12,
            color: "#e4e4e7",}}
        />
        <Legend wrapperStyle={{fontSize: 11, color: "#71717a"}} />
        <Bar dataKey="Calls" fill="#6366f1" radius={[0, 2, 2, 0]} />
        <Bar dataKey="Meetings" fill="#f59e0b" radius={[0, 2, 2, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
