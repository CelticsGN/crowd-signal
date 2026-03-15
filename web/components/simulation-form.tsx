"use client"

import { motion } from "framer-motion"
import type { FormEvent } from "react"

type Props = {
  ticker: string
  catalyst: string
  horizonMinutes: number
  loading: boolean
  onTickerChange: (value: string) => void
  onCatalystChange: (value: string) => void
  onHorizonChange: (value: number) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

const TICKERS = ["NVDA", "TSLA", "META", "AAPL", "AMD"] as const
const HORIZONS = [60, 120, 240] as const

export function SimulationForm({
  ticker,
  catalyst,
  horizonMinutes,
  loading,
  onTickerChange,
  onCatalystChange,
  onHorizonChange,
  onSubmit,
}: Props) {
  return (
    <motion.form
      onSubmit={onSubmit}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="w-full border border-foreground/20 bg-background/75 backdrop-blur-sm p-4 lg:p-6"
    >
      <div className="flex items-center gap-4 mb-5">
        <span className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">{"// SIMULATION_INPUT"}</span>
        <div className="flex-1 border-t border-border" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <label className="text-xs uppercase tracking-widest text-muted-foreground flex flex-col gap-2">
          Ticker
          <select
            value={ticker}
            onChange={(e) => onTickerChange(e.target.value)}
            className="border border-foreground/25 bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-foreground"
          >
            {TICKERS.map((symbol) => (
              <option key={symbol} value={symbol}>
                {symbol}
              </option>
            ))}
          </select>
        </label>

        <label className="text-xs uppercase tracking-widest text-muted-foreground flex flex-col gap-2">
          Horizon
          <select
            value={horizonMinutes}
            onChange={(e) => onHorizonChange(Number(e.target.value))}
            className="border border-foreground/25 bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-foreground"
          >
            {HORIZONS.map((minutes) => (
              <option key={minutes} value={minutes}>
                {minutes} minutes
              </option>
            ))}
          </select>
        </label>

        <label className="text-xs uppercase tracking-widest text-muted-foreground flex flex-col gap-2">
          Catalyst
          <input
            type="text"
            required
            value={catalyst}
            onChange={(e) => onCatalystChange(e.target.value)}
            placeholder="Earnings beat by 20%"
            className="border border-foreground/25 bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/70 outline-none focus:border-foreground"
          />
        </label>
      </div>

      <div className="mt-5 flex items-center gap-4">
        <button
          type="submit"
          disabled={loading}
          className="bg-foreground text-background px-5 py-2 text-xs font-mono tracking-widest uppercase disabled:opacity-60 disabled:cursor-wait"
        >
          {loading ? "Running..." : "Run Simulation"}
        </button>
        {loading ? (
          <span className="text-xs uppercase tracking-widest text-muted-foreground">Processing crowd graph...</span>
        ) : null}
      </div>
    </motion.form>
  )
}
