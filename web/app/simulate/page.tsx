"use client"

import { Suspense, useEffect, useRef, useState, type FormEvent } from "react"
import { motion } from "framer-motion"
import { useSearchParams } from "next/navigation"
import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { LiveSimulationFeed } from "@/components/live-simulation-feed"
import { SimulationForm } from "@/components/simulation-form"
import { SimulationResults } from "@/components/simulation-results"
import { VerdictCard } from "@/components/verdict-card"
import { useSimulationStream } from "@/hooks/useSimulationStream"

function SimulatePageContent() {
  const searchParams = useSearchParams()
  const [ticker, setTicker] = useState("NVDA")
  const [catalyst, setCatalyst] = useState("Earnings beat by 20%")
  const [horizonMinutes, setHorizonMinutes] = useState(120)
  const autoRunKeyRef = useRef<string | null>(null)

  const {
    events,
    currentTick,
    maxTicks,
    isConnected,
    isStreaming,
    isComplete,
    finalResult,
    error,
    analysisRunId,
    startSimulation,
  } = useSimulationStream()

  useEffect(() => {
    const paramTicker = (searchParams.get("ticker") || "").trim().toUpperCase()
    const paramCatalyst = (searchParams.get("catalyst") || "").trim()
    const paramHorizon = Number(searchParams.get("horizon_minutes") || searchParams.get("horizon") || "120")
    const safeHorizon = Number.isFinite(paramHorizon) ? Math.max(60, Math.min(240, Math.round(paramHorizon))) : 120

    if (paramTicker) setTicker(paramTicker)
    if (paramCatalyst) setCatalyst(paramCatalyst)
    setHorizonMinutes(safeHorizon)
  }, [searchParams])

  useEffect(() => {
    const paramTicker = (searchParams.get("ticker") || "").trim().toUpperCase()
    const paramCatalyst = (searchParams.get("catalyst") || "").trim()
    if (!paramTicker || !paramCatalyst) return

    const paramHorizon = Number(searchParams.get("horizon_minutes") || searchParams.get("horizon") || "120")
    const safeHorizon = Number.isFinite(paramHorizon) ? Math.max(60, Math.min(240, Math.round(paramHorizon))) : 120
    const runKey = `${paramTicker}|${paramCatalyst}|${safeHorizon}`

    if (autoRunKeyRef.current === runKey) return
    if (isStreaming) return

    autoRunKeyRef.current = runKey
    void startSimulation({
      ticker: paramTicker,
      catalyst: paramCatalyst,
      horizon_minutes: safeHorizon,
    })
  }, [isStreaming, searchParams, startSimulation])

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await startSimulation({
      ticker,
      catalyst,
      horizon_minutes: horizonMinutes,
    })
  }

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
          <p className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground mb-2">{"// CROWD_SIGNAL_CONSOLE"}</p>
          <h1 className="font-pixel text-3xl lg:text-5xl tracking-tight">MARKET CROWD SIMULATOR</h1>
          <p className="mt-3 text-sm text-muted-foreground max-w-3xl">
            Submit a catalyst and inspect how retail, bears, whales, and algos diverge under the same market shock.
          </p>
        </motion.section>

        <div className="space-y-5">
          <SimulationForm
            ticker={ticker}
            catalyst={catalyst}
            horizonMinutes={horizonMinutes}
            loading={isStreaming && !isComplete}
            onTickerChange={setTicker}
            onCatalystChange={setCatalyst}
            onHorizonChange={setHorizonMinutes}
            onSubmit={onSubmit}
          />

          {error ? (
            <div className="border border-destructive bg-destructive/10 px-4 py-3 text-xs font-mono uppercase tracking-wider text-destructive">
              {error}
            </div>
          ) : null}

          {finalResult?.verdict ? (
            <VerdictCard verdict={finalResult.verdict} />
          ) : null}

          {events.length > 0 ? (
            <div className="mt-8 border border-foreground/20 bg-background/80 p-4">
              <details className="group" open={!isComplete}>
                <summary className="flex cursor-pointer items-center justify-between font-mono text-xs uppercase tracking-[0.16em] text-muted-foreground outline-none">
                  <span>// CROWD_NARRATIVE_FEED</span>
                  <span className="group-open:hidden">[+] EXPAND</span>
                  <span className="hidden group-open:inline">[-] COLLAPSE</span>
                </summary>
                <div className="mt-4 pt-4 border-t border-foreground/10">
                  <LiveSimulationFeed
                    events={events}
                    currentTick={currentTick}
                    maxTicks={maxTicks}
                    isConnected={isConnected}
                    isComplete={isComplete}
                  />
                </div>
              </details>
            </div>
          ) : null}

          {finalResult ? <SimulationResults data={finalResult} analysisRunId={analysisRunId} /> : null}
        </div>
      </main>
      <Footer />
    </div>
  )
}

export default function SimulatePage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <SimulatePageContent />
    </Suspense>
  )
}
