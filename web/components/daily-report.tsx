"use client"

import { useRouter } from "next/navigation"
import { useEffect, useMemo, useState } from "react"

type DailyReportEntry = {
  ticker: string
  catalyst: string
  headline: string
  priority: string
  aggregate_stance: number
  probability_up: number
  probability_down: number
  crowd_verdict: "BULLISH" | "BEARISH" | "NEUTRAL"
  verdict_strength: "STRONG" | "MODERATE" | "WEAK"
  currency: "USD" | "INR"
}

type DailyReportResponse = {
  report_date?: string
  generated_at?: string
  us_entries: DailyReportEntry[]
  in_entries: DailyReportEntry[]
  accuracy_this_week?: number
  correct_this_week?: number
  total_this_week?: number
  status?: "ready" | "generating"
  message?: string
}

const ICON_HIGH = "\u2605"
const ICON_MEDIUM = "\u25C6"
const ICON_LOW = "\u00B7"
const FLAG_US = "\ud83c\uddfa\ud83c\uddf8"
const FLAG_IN = "\ud83c\uddee\ud83c\uddf3"
const DASH = "\u2014"
const BULLET = "\u2022"

function priorityBadge(priority: string): { icon: string; className: string } {
  const p = priority.toUpperCase()
  if (p === "HIGH") return { icon: ICON_HIGH, className: "text-amber-400" }
  if (p === "MEDIUM") return { icon: ICON_MEDIUM, className: "text-fuchsia-400" }
  return { icon: ICON_LOW, className: "text-muted-foreground" }
}

function strengthClass(strength: DailyReportEntry["verdict_strength"]): string {
  if (strength === "STRONG") return "text-foreground"
  if (strength === "MODERATE") return "text-foreground/80"
  return "text-muted-foreground"
}

function verdictClass(verdict: DailyReportEntry["crowd_verdict"]): string {
  if (verdict === "BULLISH") return "text-emerald-400"
  if (verdict === "BEARISH") return "text-rose-400"
  return "text-zinc-400"
}

function truncateHeadline(text: string): string {
  const clean = (text || "").trim()
  if (clean.length <= 50) return clean
  return `${clean.slice(0, 50)}...`
}

function verdictBar(entry: DailyReportEntry): string {
  const full = "\u2588"
  const empty = "\u2591"
  const maxProb = Math.max(entry.probability_up, entry.probability_down)
  const fill = Math.max(1, Math.min(10, Math.round(maxProb * 10)))

  if (entry.crowd_verdict === "BULLISH") {
    return `${full.repeat(fill)}${empty.repeat(10 - fill)}`
  }

  if (entry.crowd_verdict === "BEARISH") {
    return `${empty.repeat(10 - fill)}${full.repeat(fill)}`
  }

  const neutralFill = Math.max(2, Math.min(6, Math.round(fill * 0.6)))
  const left = Math.floor((10 - neutralFill) / 2)
  const right = 10 - neutralFill - left
  return `${empty.repeat(left)}${full.repeat(neutralFill)}${empty.repeat(right)}`
}

function formatTime(value?: string): string {
  if (!value) return ""
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ""
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

function ReportRow({ entry }: { entry: DailyReportEntry }) {
  const router = useRouter()
  const strongest = Math.max(entry.probability_up, entry.probability_down)
  const percent = `${Math.round(strongest * 100)}%`
  const priority = priorityBadge(entry.priority)

  return (
    <button
      type="button"
      onClick={() =>
        router.push(
          `/simulate?ticker=${encodeURIComponent(entry.ticker)}&catalyst=${encodeURIComponent(entry.catalyst)}`,
        )
      }
      className="w-full border-b border-foreground/15 py-2 text-left hover:bg-foreground/5 transition-colors"
    >
      <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.12em]">
        <span className="w-28 shrink-0 text-foreground">{entry.ticker}</span>
        <span className={`w-24 shrink-0 ${verdictClass(entry.crowd_verdict)}`}>{verdictBar(entry)}</span>
        <span className={`w-16 shrink-0 ${verdictClass(entry.crowd_verdict)}`}>{entry.crowd_verdict}</span>
        <span className="w-12 shrink-0 text-foreground">{percent}</span>
        <span className={`w-16 shrink-0 ${priority.className}`}>{priority.icon}</span>
        <span className={`w-20 shrink-0 ${strengthClass(entry.verdict_strength)}`}>{entry.verdict_strength}</span>
      </div>
      <p className="mt-1 pl-28 text-xs text-muted-foreground leading-relaxed">
        "{truncateHeadline(entry.headline)}"
      </p>
    </button>
  )
}

export function DailyReport() {
  const [loading, setLoading] = useState(true)
  const [report, setReport] = useState<DailyReportResponse | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let alive = true

    const pull = async () => {
      try {
        const res = await fetch("/api/daily-report", { cache: "no-store" })
        if (!res.ok) {
          if (!alive) return
          setFailed(true)
          setLoading(false)
          return
        }

        const payload = (await res.json()) as DailyReportResponse
        if (!alive) return
        setReport(payload)
        setFailed(false)
        setLoading(false)
      } catch {
        if (!alive) return
        setFailed(true)
        setLoading(false)
      }
    }

    void pull()
    const timer = window.setInterval(pull, 5 * 60 * 1000)

    return () => {
      alive = false
      window.clearInterval(timer)
    }
  }, [])

  const accuracyLine = useMemo(() => {
    if (!report) return ""
    const total = report.total_this_week ?? 0
    const correct = report.correct_this_week ?? 0
    const acc = Math.round(report.accuracy_this_week ?? 0)
    if (total < 5) return "// CALIBRATING"
    return `Accuracy this week: ${acc}% (${correct}/${total} correct)`
  }, [report])

  if (failed) {
    return (
      <div className="mt-6 w-full border border-destructive/40 bg-destructive/10 p-4 lg:p-6">
        <p className="text-xs font-mono uppercase tracking-[0.16em] text-destructive">// REPORT_UNAVAILABLE</p>
        <p className="mt-2 text-sm text-foreground/90">Could not reach backend.</p>
        <p className="mt-1 text-xs text-muted-foreground">Check: crowd-signal.onrender.com/health</p>
      </div>
    )
  }

  if (loading) {
    return <p className="mt-4 text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">// GENERATING_DAILY_REPORT...</p>
  }

  if (!report || report.status === "generating") {
    return (
      <div className="mt-6 w-full border border-foreground/20 bg-background/70 p-4 lg:p-6 backdrop-blur-sm">
        <p className="text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">// REPORT_PENDING</p>
        <p className="mt-2 text-sm text-foreground/90">Daily scan has not run yet today.</p>
        <p className="mt-1 text-xs text-muted-foreground">Trigger manually: POST /api/v1/daily-report/trigger</p>
      </div>
    )
  }

  const isEmpty = report.us_entries.length === 0 && report.in_entries.length === 0
  if (isEmpty) {
    return (
      <div className="mt-6 w-full border border-foreground/20 bg-background/70 p-4 lg:p-6 backdrop-blur-sm">
        <p className="text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">// REPORT_EMPTY</p>
        <p className="mt-2 text-sm text-foreground/90">Report generated but no catalysts found today.</p>
        <p className="mt-2 text-xs text-muted-foreground">Possible causes:</p>
        <p className="mt-1 text-xs text-muted-foreground">- News feeds returned no headlines</p>
        <p className="text-xs text-muted-foreground">- All tickers below activity threshold</p>
        <p className="text-xs text-muted-foreground">- Check backend logs for [SCANNER] and [NEWS] entries</p>
      </div>
    )
  }

  return (
    <div className="mt-6 w-full border border-foreground/20 bg-background/70 p-4 lg:p-6 backdrop-blur-sm">
      <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{`// CROWD_SIGNAL_DAILY ${DASH} ${report.report_date}`}</p>
      <p className="mt-2 text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">
        {`Generated at ${formatTime(report.generated_at)} ${BULLET} ${accuracyLine}`}
      </p>

      <div className="mt-5">
        <p className="text-xs font-mono uppercase tracking-[0.16em] text-foreground">{`${FLAG_US} US MARKETS`}</p>
        <div className="mt-2 border-t border-border" />
        <div className="mt-1">
          {report.us_entries.length > 0 ? report.us_entries.map((entry) => <ReportRow key={`${entry.ticker}_${entry.headline}`} entry={entry} />) : (
            <p className="py-3 text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">No major catalyst today</p>
          )}
        </div>
      </div>

      <div className="mt-6">
        <p className="text-xs font-mono uppercase tracking-[0.16em] text-foreground">{`${FLAG_IN} NSE MARKETS`}</p>
        <div className="mt-2 border-t border-border" />
        <div className="mt-1">
          {report.in_entries.length > 0 ? report.in_entries.map((entry) => <ReportRow key={`${entry.ticker}_${entry.headline}`} entry={entry} />) : (
            <p className="py-3 text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">No major catalyst today</p>
          )}
        </div>
      </div>
    </div>
  )
}
