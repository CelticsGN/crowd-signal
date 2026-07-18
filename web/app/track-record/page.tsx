"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { AccuracyBadge } from "@/components/accuracy-badge"

type RecentRunEntry = {
  ticker: string
  action: string
  confidence?: number
  entry_price?: number
  target_price?: number
  stop_price?: number
  range_low?: number
  range_high?: number
  prediction_correct?: boolean
  actual_price_24h?: number
  created_at: string
}

type RecentRunsResponse = {
  runs: RecentRunEntry[]
}

export default function TrackRecordPage() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [recentRuns, setRecentRuns] = useState<RecentRunEntry[]>([])

  useEffect(() => {
    let mounted = true
    const fetchRecentRuns = async () => {
      try {
        const response = await fetch("/api/accuracy/recent", { cache: "no-store" })
        if (!response.ok) {
          if (mounted) {
            setError(true)
            setLoading(false)
          }
          return
        }

        const payload = (await response.json()) as RecentRunsResponse
        if (!mounted) return
        setRecentRuns(payload.runs || [])
        setError(false)
        setLoading(false)
      } catch {
        if (!mounted) return
        setError(true)
        setLoading(false)
      }
    }
    void fetchRecentRuns()
  }, [])

  return (
    <div className="min-h-screen dot-grid-bg">
      <Navbar />
      <main className="w-full px-6 py-8 lg:px-12 lg:py-10">
        <motion.section
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
          className="w-full border border-foreground/20 bg-background/75 backdrop-blur-sm p-6 mb-5"
        >
          <p className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground mb-2">{"// TRACK_RECORD"}</p>
          <h1 className="font-pixel text-3xl lg:text-5xl tracking-tight">CROWD ACCURACY</h1>
          <p className="mt-3 text-sm text-muted-foreground max-w-3xl">
            Real-time tracking of AI simulation accuracy over a 24-hour horizon.
          </p>
        </motion.section>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-8">
          <AccuracyBadge />
        </div>

        <motion.section
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="w-full border border-foreground/20 bg-background/80 p-5"
        >
          <div className="flex items-center gap-4 mb-5">
            <span className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">// RECENT_SCORED_RUNS</span>
            <div className="flex-1 border-t border-border" />
          </div>

          {loading ? (
            <div className="py-8 text-center">
              <p className="text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">
                // LOADING_HISTORY
              </p>
            </div>
          ) : error ? (
            <div className="border border-destructive bg-destructive/10 px-4 py-3 text-xs font-mono uppercase tracking-wider text-destructive">
              Failed to load recent runs history.
            </div>
          ) : recentRuns.length === 0 ? (
            <div className="py-8 text-center border border-dashed border-foreground/20">
              <p className="text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">
                // TRACK_RECORD_BUILDING - first results in ~24h
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono text-left">
                <thead className="bg-muted/30">
                  <tr>
                    <th className="py-2 px-3 uppercase tracking-wider font-normal text-muted-foreground border-b border-foreground/10">Date</th>
                    <th className="py-2 px-3 uppercase tracking-wider font-normal text-muted-foreground border-b border-foreground/10">Ticker</th>
                    <th className="py-2 px-3 uppercase tracking-wider font-normal text-muted-foreground border-b border-foreground/10">Action</th>
                    <th className="py-2 px-3 uppercase tracking-wider font-normal text-muted-foreground border-b border-foreground/10">Confidence</th>
                    <th className="py-2 px-3 uppercase tracking-wider font-normal text-muted-foreground border-b border-foreground/10">Targets</th>
                    <th className="py-2 px-3 uppercase tracking-wider font-normal text-muted-foreground border-b border-foreground/10">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {recentRuns.map((run, i) => {
                    const isBuy = run.action === "BUY"
                    const isSell = run.action === "SELL"
                    const actionColor = isBuy ? "text-emerald-500" : isSell ? "text-rose-500" : "text-muted-foreground"
                    
                    const isCorrect = run.prediction_correct === true
                    const isWrong = run.prediction_correct === false
                    const resultLabel = isCorrect ? "CORRECT" : isWrong ? "INCORRECT" : "PENDING"
                    const resultColor = isCorrect ? "text-emerald-500" : isWrong ? "text-rose-500" : "text-muted-foreground"

                    return (
                      <tr key={`${run.ticker}-${run.created_at}-${i}`} className="border-b border-foreground/5 hover:bg-foreground/5 transition-colors">
                        <td className="py-3 px-3 text-muted-foreground">
                          {new Date(run.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                        </td>
                        <td className="py-3 px-3 font-semibold text-foreground">{run.ticker}</td>
                        <td className={`py-3 px-3 font-bold ${actionColor}`}>{run.action}</td>
                        <td className="py-3 px-3 text-muted-foreground">{run.confidence ? `${run.confidence}%` : "—"}</td>
                        <td className="py-3 px-3 text-muted-foreground">
                          {(isBuy || isSell) ? (
                            <span>E: {run.entry_price?.toFixed(2) ?? "—"} / T: {run.target_price?.toFixed(2) ?? "—"}</span>
                          ) : (
                            <span>R: {run.range_low?.toFixed(2) ?? "—"} - {run.range_high?.toFixed(2) ?? "—"}</span>
                          )}
                        </td>
                        <td className={`py-3 px-3 font-bold ${resultColor}`}>{resultLabel}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </motion.section>
      </main>
      <Footer />
    </div>
  )
}
