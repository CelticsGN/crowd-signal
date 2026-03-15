"use client"

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import type { PersonaResult } from "@/hooks/useSimulation"

type Props = {
  personas: PersonaResult[]
}

const COLORS: Record<string, string> = {
  retail_bull: "#ea580c",
  retail_bear: "#2563eb",
  whale: "#0f766e",
  algo: "#7c3aed",
}

export function SimulationPersonaChart({ personas }: Props) {
  return (
    <div className="h-[320px] w-full border border-foreground/20 bg-background/80 p-3">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={personas} margin={{ top: 12, right: 20, left: 0, bottom: 6 }}>
          <CartesianGrid strokeDasharray="2 2" stroke="hsl(var(--border))" />
          <XAxis dataKey="persona" stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 12 }} />
          <YAxis domain={[-1, 1]} stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 12 }} />
          <ReferenceLine y={0} stroke="hsl(var(--foreground))" strokeOpacity={0.5} />
          <Tooltip
            cursor={{ fill: "hsl(var(--muted) / 0.35)" }}
            contentStyle={{
              background: "hsl(var(--background))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 0,
              fontSize: 12,
            }}
            formatter={(value: number, key: string) => [value.toFixed(3), key]}
          />
          <Bar dataKey="stance" name="Stance" radius={0}>
            {personas.map((item) => (
              <Cell key={item.persona} fill={COLORS[item.persona] ?? "hsl(var(--foreground))"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
