"use client"

import { useEffect, useMemo, useRef } from "react"
import { motion } from "framer-motion"
import type { SimulationStreamEvent } from "@/hooks/useSimulationStream"

type Props = {
  events: SimulationStreamEvent[]
  currentTick: number
  maxTicks: number
  isConnected: boolean
  isComplete: boolean
}

function formatEventLabel(type: string): string {
  return type.replaceAll("_", " ").toUpperCase()
}

function colorForEvent(type: string): string {
  if (type === "error") return "text-destructive"
  if (type === "narrator_error") return "text-amber-400"
  if (type === "complete") return "text-emerald-400"
  if (type === "herd_detected") return "text-amber-400"
  if (type === "agent_thought") return "text-cyan-300"
  if (type === "narrator") return "text-lime-300"
  return "text-foreground"
}

function stringifyEvent(event: SimulationStreamEvent): string {
  if (event.type === "tick") {
    const tick = Number(event.tick ?? 0)
    const total = Number(event.max_ticks ?? 0)
    const mean = Number(event.mean_stance ?? 0)
    return `Tick ${tick}/${total} | mean=${mean.toFixed(3)}`
  }

  if (event.type === "herd_detected") {
    const direction = String(event.direction ?? "unknown")
    const strength = Number(event.strength ?? 0)
    return `Herd detected: ${direction} (${(strength * 100).toFixed(1)}%)`
  }

  if (event.type === "agent_thought") {
    return String(event.message ?? "Agent thought received")
  }

  if (event.type === "narrator") {
    return String(event.message ?? "Narrator summary available")
  }

  if (event.type === "narrator_error") {
    return "// NARRATOR_UNAVAILABLE - Groq rate limit or timeout"
  }

  if (event.type === "error") {
    return String(event.message ?? "Stream error")
  }

  return JSON.stringify(event)
}

export function LiveSimulationFeed({ events, currentTick, maxTicks, isConnected, isComplete }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const progressPct = maxTicks > 0 ? Math.min(100, (currentTick / maxTicks) * 100) : 0

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [events])

  const herdWarning = useMemo(
    () => events.findLast((entry) => entry.type === "herd_detected") ?? null,
    [events],
  )

  const latestError = useMemo(
    () => events.findLast((entry) => entry.type === "error") ?? null,
    [events],
  )

  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="w-full border border-foreground/20 bg-background/80 backdrop-blur-sm p-4 lg:p-6"
    >
      <div className="flex items-center gap-4 mb-5">
        <span className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">{"// LIVE_STREAM"}</span>
        <div className="flex-1 border-t border-border" />
        <span className={`text-[10px] font-mono uppercase tracking-[0.16em] ${isConnected ? "text-emerald-400" : "text-amber-400"}`}>
          {isConnected ? "ws_connected" : "ws_disconnected"}
        </span>
      </div>

      <div className="mb-4">
        <div className="h-2 w-full border border-foreground/20 bg-background">
          <div className="h-full bg-foreground/70 transition-[width] duration-200" style={{ width: `${progressPct}%` }} />
        </div>
        <p className="mt-2 text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">
          Progress {currentTick}/{maxTicks || "-"}
        </p>
      </div>

      {herdWarning ? (
        <div className="mb-4 border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-xs font-mono uppercase tracking-[0.14em] text-amber-300">
          {stringifyEvent(herdWarning)}
        </div>
      ) : null}

      {latestError ? (
        <div className="mb-4 border border-destructive/60 bg-destructive/10 px-3 py-2 text-xs font-mono tracking-[0.08em] text-destructive">
          <p className="uppercase">// SIMULATION_ERROR</p>
          <p className="mt-1">{String(latestError.message ?? "Simulation stream failed")}</p>
          <p className="mt-1 text-muted-foreground">Retrying with standard mode...</p>
        </div>
      ) : null}

      <div ref={scrollRef} className="max-h-72 overflow-y-auto border border-foreground/20 bg-background/70 p-3 space-y-2">
        {events.length === 0 ? (
          <p className="text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">Awaiting stream events...</p>
        ) : null}

        {events.map((entry, index) => (
          <div key={`${entry.type}_${index}`} className="text-xs font-mono leading-relaxed">
            <span className={`mr-2 ${colorForEvent(entry.type)}`}>[{formatEventLabel(entry.type)}]</span>
            <span className="text-foreground/90">{stringifyEvent(entry)}</span>
          </div>
        ))}
      </div>

      {isComplete ? (
        <p className="mt-4 text-xs font-mono uppercase tracking-[0.14em] text-emerald-400">Simulation complete. Final summary ready.</p>
      ) : null}
    </motion.section>
  )
}
