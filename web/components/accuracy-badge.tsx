"use client"

import { useEffect, useMemo, useState } from "react"

type TickerAccuracyEntry = {
  total: number
  correct: number
  accuracy_pct: number
}

type AccuracyStats = {
  global_accuracy: TickerAccuracyEntry
  by_ticker: Record<string, TickerAccuracyEntry>
  last_updated: string
}

type AccuracyBadgeProps = {
  compact?: boolean
}

function toPct(value: number): string {
  return `${value.toFixed(1)}%`
}

function currencyTagForTicker(ticker: string): string {
  return ticker.endsWith(".NS") || ticker.endsWith(".BO") ? "₹ INR" : "$ USD"
}

export function AccuracyBadge({ compact = false }: AccuracyBadgeProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [stats, setStats] = useState<AccuracyStats | null>(null)

  useEffect(() => {
    let mounted = true

    const fetchAccuracy = async () => {
      try {
        const response = await fetch("/api/accuracy", { cache: "no-store" })
        if (!response.ok) {
          if (mounted) {
            setError(true)
            setLoading(false)
          }
          return
        }

        const payload = (await response.json()) as AccuracyStats
        if (!mounted) return
        setStats(payload)
        setError(false)
        setLoading(false)
      } catch {
        if (!mounted) return
        setError(true)
        setLoading(false)
      }
    }

    void fetchAccuracy()
    const intervalId = window.setInterval(fetchAccuracy, 5 * 60 * 1000)

    return () => {
      mounted = false
      window.clearInterval(intervalId)
    }
  }, [])

  const topTickers = useMemo(() => {
    if (!stats?.by_ticker) return []
    return Object.entries(stats.by_ticker)
      .sort((a, b) => (b[1]?.total ?? 0) - (a[1]?.total ?? 0))
      .slice(0, 3)
  }, [stats])

  if (error) return null

  if (loading) {
    return (
      <section className="w-full border border-foreground/20 bg-background/80 p-4">
        <p className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">// PREDICTION_ACCURACY</p>
        <p className="mt-2 text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">// LOADING_ACCURACY</p>
      </section>
    )
  }

  if (!stats) return null

  const global = stats.global_accuracy
  const calibrating = (global?.total ?? 0) < 20

  if (compact) {
    return (
      <section className="w-full border border-foreground/20 bg-background/80 p-3">
        <p className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">// PREDICTION_ACCURACY</p>
        {calibrating ? (
          <p className="mt-2 text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">
            // CALIBRATING - insufficient data
          </p>
        ) : (
          <p className="mt-2 text-xs font-mono uppercase tracking-[0.16em] text-foreground">
            {toPct(global.accuracy_pct)} directional accuracy across {global.total} runs
          </p>
        )}
      </section>
    )
  }

  return (
    <section className="w-full max-w-md border border-foreground/20 bg-background/80 p-4">
      <p className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">// PREDICTION_ACCURACY</p>

      {calibrating ? (
        <p className="mt-4 text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">
          // CALIBRATING - insufficient data
        </p>
      ) : (
        <>
          <p className="mt-4 text-4xl font-semibold text-foreground">{toPct(global.accuracy_pct)}</p>
          <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">directional accuracy across {global.total} runs</p>

          {topTickers.length > 0 ? (
            <div className="mt-4 space-y-1 border-t border-foreground/20 pt-3">
              {topTickers.map(([ticker, entry]) => (
                <div key={ticker} className="flex items-center justify-between text-xs font-mono uppercase tracking-[0.16em]">
                  <span className="text-foreground">{ticker}</span>
                  <span className="text-muted-foreground">{Math.round(entry.accuracy_pct)}% ({entry.total} runs) {currencyTagForTicker(ticker)}</span>
                </div>
              ))}
            </div>
          ) : null}
        </>
      )}
    </section>
  )
}
