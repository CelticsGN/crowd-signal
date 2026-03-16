"use client"

import { motion } from "framer-motion"
import Link from "next/link"
import type { SimulateResponse } from "@/hooks/useSimulation"
import { SimulationPersonaChart } from "@/components/simulation-persona-chart"

type Props = {
  data: SimulateResponse
  analysisRunId?: string | null
}

function toPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

export function SimulationResults({ data, analysisRunId }: Props) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="w-full border border-foreground/20 bg-background/80 backdrop-blur-sm p-4 lg:p-6"
    >
      <div className="flex items-center gap-4 mb-5">
        <span className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">{"// SIMULATION_OUTPUT"}</span>
        <div className="flex-1 border-t border-border" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
        <Metric label="Aggregate Stance" value={data.aggregate_stance.toFixed(3)} />
        <Metric label="Probability Up" value={toPercent(data.probability_up)} />
        <Metric label="Probability Down" value={toPercent(data.probability_down)} />
      </div>

      <SimulationPersonaChart personas={data.personas} />

      <div className="mt-5 overflow-x-auto border border-foreground/20">
        <table className="w-full text-xs font-mono">
          <thead className="bg-muted/30">
            <tr>
              <th className="text-left py-2 px-3 uppercase tracking-wider">Persona</th>
              <th className="text-right py-2 px-3 uppercase tracking-wider">Stance</th>
              <th className="text-right py-2 px-3 uppercase tracking-wider">Confidence</th>
              <th className="text-right py-2 px-3 uppercase tracking-wider">Weight</th>
            </tr>
          </thead>
          <tbody>
            {data.personas.map((persona) => (
              <tr key={persona.persona} className="border-t border-border/70">
                <td className="py-2 px-3">{persona.persona}</td>
                <td className="py-2 px-3 text-right">{persona.stance.toFixed(3)}</td>
                <td className="py-2 px-3 text-right">{persona.confidence.toFixed(3)}</td>
                <td className="py-2 px-3 text-right">{toPercent(persona.weight)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {analysisRunId ? (
        <div className="mt-5">
          <Link
            href={`/analysis/${analysisRunId}`}
            className="inline-flex border border-foreground/30 px-4 py-2 text-xs font-mono uppercase tracking-[0.16em] text-foreground hover:bg-foreground/10 transition-colors"
          >
            // VIEW_FULL_ANALYSIS →
          </Link>
        </div>
      ) : null}

      <p className="mt-4 text-xs text-muted-foreground uppercase tracking-wider">
        This is not financial advice. Probabilistic simulation only.
      </p>
    </motion.section>
  )
}

type MetricProps = {
  label: string
  value: string
}

function Metric({ label, value }: MetricProps) {
  return (
    <article className="border border-foreground/20 bg-background px-3 py-3">
      <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </article>
  )
}
