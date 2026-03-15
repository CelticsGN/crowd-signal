"use client"

import { useState, type FormEvent } from "react"
import { motion } from "framer-motion"
import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { SimulationForm } from "@/components/simulation-form"
import { SimulationResults } from "@/components/simulation-results"
import { useSimulation } from "@/hooks/useSimulation"

export default function SimulatePage() {
  const [ticker, setTicker] = useState("NVDA")
  const [catalyst, setCatalyst] = useState("Earnings beat by 20%")
  const [horizonMinutes, setHorizonMinutes] = useState(120)

  const { data, loading, error, runSimulation } = useSimulation()

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await runSimulation({
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
            loading={loading}
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

          {data ? <SimulationResults data={data} /> : null}
        </div>
      </main>
      <Footer />
    </div>
  )
}
