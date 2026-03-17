"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { useEffect, useMemo, useState } from "react"
import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { CatalystGraph } from "@/components/catalyst-graph"
import { CrowdNarrative } from "@/components/crowd-narrative"
import { AccuracyBadge } from "@/components/accuracy-badge"
import type { SimulateResponse, StoredSimulationRun } from "@/hooks/useSimulation"

function toPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function toTimeAgo(dateString: string): string {
  const timestamp = new Date(dateString).getTime()
  if (Number.isNaN(timestamp)) return "unknown time"
  const diffMs = Date.now() - timestamp
  const diffMinutes = Math.max(1, Math.floor(diffMs / 60000))
  if (diffMinutes < 60) return `${diffMinutes} minutes ago`
  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours} hours ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays} days ago`
}

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return "{}"
  }
}

export default function AnalysisPage() {
  const params = useParams<{ id: string }>()
  const runId = params?.id ?? ""

  const [storedRun, setStoredRun] = useState<StoredSimulationRun | null>(null)
  const [expired, setExpired] = useState(false)

  useEffect(() => {
    if (!runId) {
      setExpired(true)
      return
    }

    try {
      const raw = sessionStorage.getItem(`simulation_run_${runId}`)
      if (!raw) {
        setExpired(true)
        return
      }
      const parsed = JSON.parse(raw) as StoredSimulationRun
      if (!parsed?.result) {
        setExpired(true)
        return
      }
      setStoredRun(parsed)
    } catch {
      setExpired(true)
    }
  }, [runId])

  const result: SimulateResponse | null = storedRun?.result ?? null

  const extractionJson = useMemo(() => {
    if (!result?.catalyst_analysis) return "{}"
    return safeJson(result.catalyst_analysis)
  }, [result])

  return (
    <div className="min-h-screen dot-grid-bg">
      <Navbar />
      <main className="w-full px-6 py-8 lg:px-12 lg:py-10 space-y-5">
        {expired || !result ? (
          <section className="w-full border border-foreground/20 bg-background/80 p-6">
            <p className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground mb-3">// ANALYSIS</p>
            <p className="text-sm font-mono uppercase tracking-[0.14em] text-muted-foreground">// SESSION_EXPIRED - run a new simulation</p>
            <Link
              href="/simulate"
              className="mt-4 inline-flex border border-foreground/30 px-4 py-2 text-xs font-mono uppercase tracking-[0.16em] hover:bg-foreground/10 transition-colors"
            >
              ← back to simulator
            </Link>
          </section>
        ) : (
          <>
            <section className="w-full border border-foreground/20 bg-background/80 p-6">
              <Link
                href="/simulate"
                className="inline-flex mb-4 border border-foreground/30 px-3 py-1 text-xs font-mono uppercase tracking-[0.16em] hover:bg-foreground/10 transition-colors"
              >
                ← back to simulator
              </Link>
              <p className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground mb-2">// ANALYSIS_CONSOLE</p>
              <h1 className="font-pixel text-4xl lg:text-6xl tracking-tight">{result.ticker}</h1>
              <p className="mt-3 text-sm text-foreground">{result.catalyst}</p>
              <p className="mt-3 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                {new Date(storedRun?.createdAt ?? "").toLocaleString()}
              </p>
              <div className="mt-4 max-w-sm">
                <AccuracyBadge compact />
              </div>
            </section>

            <section className="w-full border border-foreground/20 bg-background/80 p-5">
              <div className="flex items-center gap-4 mb-4">
                <span className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">// KEY_METRICS</span>
                <div className="flex-1 border-t border-border" />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
                <Metric label="Aggregate Stance" value={result.aggregate_stance.toFixed(3)} />
                <Metric label="Probability Up" value={toPercent(result.probability_up)} />
                <Metric label="Probability Down" value={toPercent(result.probability_down)} />
              </div>

              <div className="overflow-x-auto border border-foreground/20">
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
                    {result.personas.map((persona) => (
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
            </section>

            {result.catalyst_analysis ? (
              <section className="w-full border border-foreground/20 bg-background/80 p-5">
                <div className="flex items-center gap-4 mb-4">
                  <span className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">// CATALYST_INTELLIGENCE</span>
                  <div className="flex-1 border-t border-border" />
                </div>
                <CatalystGraph analysis={result.catalyst_analysis} mode="analysis" height={500} showCounts />
              </section>
            ) : null}

            {(result.crowd_narrative ?? []).length > 0 ? (
              <section className="w-full border border-foreground/20 bg-background/80 p-5">
                <div className="flex items-center gap-4 mb-4">
                  <span className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">// CROWD_NARRATIVE</span>
                  <div className="flex-1 border-t border-border" />
                </div>
                <CrowdNarrative crowdNarrative={result.crowd_narrative ?? []} />
              </section>
            ) : null}

            {result.catalyst_analysis ? (
              <section className="w-full border border-foreground/20 bg-background/80 p-5">
                <div className="flex items-center gap-4 mb-4">
                  <span className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">// REASONING_CHAIN</span>
                  <div className="flex-1 border-t border-border" />
                </div>
                <div className="space-y-3">
                  {(result.catalyst_analysis.reasoning ?? []).map((entry, index) => {
                    const adjustment = entry.adjustment ?? entry.weight ?? 0
                    const description = entry.description ?? entry.detail ?? ""
                    const toneClass = adjustment > 0
                      ? "border-green-600/40"
                      : adjustment < 0
                        ? "border-red-600/40"
                        : "border-foreground/20"
                    const valueClass = adjustment > 0
                      ? "text-green-500"
                      : adjustment < 0
                        ? "text-red-500"
                        : "text-muted-foreground"
                    return (
                      <article key={`${entry.rule}-${index}`} className={`w-full border bg-background/50 p-4 ${toneClass}`}>
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <p className="text-[11px] uppercase tracking-[0.18em] font-mono text-foreground">{entry.rule}</p>
                            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{description}</p>
                          </div>
                          <p className={`text-xl font-mono font-bold ${valueClass}`}>
                            {adjustment >= 0 ? `+${adjustment.toFixed(3)}` : adjustment.toFixed(3)}
                          </p>
                        </div>
                      </article>
                    )
                  })}
                </div>
              </section>
            ) : null}

            <section className="w-full border border-foreground/20 bg-background/80 p-5">
              <div className="flex items-center gap-4 mb-4">
                <span className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">// PRIOR_CROWD_MEMORY</span>
                <div className="flex-1 border-t border-border" />
              </div>
              {(result.memory_context ?? []).length > 0 ? (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                  {(result.memory_context ?? []).slice(0, 3).map((entry, index) => (
                    <article key={`${entry.created_at}-${index}`} className="border border-foreground/20 bg-background/50 p-3">
                      <p className="text-xs text-foreground leading-relaxed">{entry.catalyst}</p>
                      <p className="mt-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">probability_up: {toPercent(entry.probability_up)}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">direction: {entry.direction}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">{toTimeAgo(entry.created_at)}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">
                  // NO_PRIOR_MEMORY - first simulation for ticker
                </p>
              )}
            </section>

            <section className="w-full border border-foreground/20 bg-background/80 p-5">
              <details>
                <summary className="cursor-pointer select-none text-[10px] tracking-[0.2em] uppercase text-muted-foreground">
                  // RAW_CATALYST_EXTRACTION
                </summary>
                <pre className="mt-4 overflow-x-auto border border-foreground/20 bg-background/60 p-4 text-xs font-mono text-foreground">
{extractionJson}
                </pre>
              </details>
            </section>
          </>
        )}
      </main>
      <Footer />
    </div>
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
