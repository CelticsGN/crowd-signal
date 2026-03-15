"use client"

import { useEffect, useState } from "react"
import { ArrowRight, Check, Minus } from "lucide-react"
import { motion } from "framer-motion"

const ease = [0.22, 1, 0.36, 1] as const

function ScrambleValue({ target }: { target: string }) {
  const [display, setDisplay] = useState(target.replace(/[0-9]/g, "0"))

  useEffect(() => {
    let iterations = 0
    const maxIterations = 18
    const interval = setInterval(() => {
      if (iterations >= maxIterations) {
        setDisplay(target)
        clearInterval(interval)
        return
      }
      setDisplay(
        target
          .split("")
          .map((char, i) => {
            if (!/[0-9]/.test(char)) return char
            if (iterations > maxIterations - 5 && i < iterations - (maxIterations - 5)) return char
            return String(Math.floor(Math.random() * 10))
          })
          .join(""),
      )
      iterations++
    }, 50)
    return () => clearInterval(interval)
  }, [target])

  return (
    <span className="font-mono font-bold" style={{ fontVariantNumeric: "tabular-nums" }}>
      {display}
    </span>
  )
}

function StatusLine() {
  const [throughput, setThroughput] = useState("0.0")

  useEffect(() => {
    const interval = setInterval(() => {
      setThroughput((Math.random() * 50 + 10).toFixed(1))
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex items-center gap-2 text-[10px] tracking-widest text-muted-foreground uppercase font-mono">
      <span className="h-1.5 w-1.5 bg-[#ea580c]" />
      <span>live simulation throughput: {throughput}k ticks/s</span>
    </div>
  )
}

function BlinkDot() {
  return <span className="inline-block h-2 w-2 bg-[#ea580c] animate-blink" />
}

interface Principle {
  id: string
  name: string
  rank: string
  period: string
  tag: string | null
  description: string
  features: { text: string; included: boolean }[]
  cta: string
  highlighted: boolean
}

const PRINCIPLES: Principle[] = [
  {
    id: "assistive",
    name: "ASSISTIVE",
    rank: "01",
    period: " / PRINCIPLE",
    tag: null,
    description: "Assistive, not automated: suggestions only with no trade execution.",
    features: [
      { text: "Ticker + catalyst input", included: true },
      { text: "Crowd reaction map", included: true },
      { text: "Human decision remains final", included: true },
      { text: "No broker execution", included: false },
      { text: "No guaranteed outcomes", included: false },
      { text: "No financial advice", included: false },
    ],
    cta: "PRINCIPLE 01",
    highlighted: false,
  },
  {
    id: "probabilistic",
    name: "PROBABILISTIC",
    rank: "02",
    period: " / PRINCIPLE",
    tag: "CORE",
    description: "Probabilistic, not certain: outputs are distributions with confidence.",
    features: [
      { text: "Agent stances in [-1.0, +1.0]", included: true },
      { text: "Per-persona confidence scores", included: true },
      { text: "probability_up / probability_down", included: true },
      { text: "No certainty claims", included: false },
      { text: "No deterministic forecasts", included: false },
      { text: "No guaranteed edge", included: false },
    ],
    cta: "PRINCIPLE 02",
    highlighted: true,
  },
  {
    id: "explainable",
    name: "EXPLAINABLE",
    rank: "03",
    period: " / PRINCIPLE",
    tag: null,
    description: "Explainable and honest: clear reasoning and transparent limits.",
    features: [
      { text: "Archetype-level output breakdown", included: true },
      { text: "Catalyst and crowd influence visible", included: true },
      { text: "Plain-language constraints", included: true },
      { text: "No hidden black box promises", included: false },
      { text: "No overclaiming", included: false },
      { text: "No investment advice", included: false },
    ],
    cta: "PRINCIPLE 03",
    highlighted: false,
  },
]

function PrincipleCard({ principle, index }: { principle: Principle; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30, filter: "blur(4px)" }}
      whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ delay: index * 0.12, duration: 0.6, ease }}
      className={`flex flex-col h-full ${
        principle.highlighted
          ? "border-2 border-foreground bg-foreground text-background"
          : "border-2 border-foreground bg-background text-foreground"
      }`}
    >
      <div
        className={`flex items-center justify-between px-5 py-3 border-b-2 ${
          principle.highlighted ? "border-background/20" : "border-foreground"
        }`}
      >
        <span className="text-[10px] tracking-[0.2em] uppercase font-mono">{principle.name}</span>
        <div className="flex items-center gap-2">
          {principle.tag ? (
            <span className="bg-[#ea580c] text-background text-[9px] tracking-[0.15em] uppercase px-2 py-0.5 font-mono">
              {principle.tag}
            </span>
          ) : null}
          <span className="text-[10px] tracking-[0.2em] font-mono opacity-50">
            {String(index + 1).padStart(2, "0")}
          </span>
        </div>
      </div>

      <div className="px-5 pt-6 pb-4">
        <div className="flex items-baseline gap-1">
          <span className="text-3xl lg:text-4xl">
            <ScrambleValue target={principle.rank} />
          </span>
          <span
            className={`text-xs font-mono tracking-widest uppercase ${
              principle.highlighted ? "text-background/50" : "text-muted-foreground"
            }`}
          >
            {principle.period}
          </span>
        </div>
        <p
          className={`text-xs font-mono mt-3 leading-relaxed ${
            principle.highlighted ? "text-background/60" : "text-muted-foreground"
          }`}
        >
          {principle.description}
        </p>
      </div>

      <div
        className={`flex-1 px-5 py-4 border-t-2 ${
          principle.highlighted ? "border-background/20" : "border-foreground"
        }`}
      >
        <div className="flex flex-col gap-3">
          {principle.features.map((feature, fi) => (
            <motion.div
              key={feature.text}
              initial={{ opacity: 0, x: -8 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.12 + 0.3 + fi * 0.04, duration: 0.35, ease }}
              className="flex items-start gap-3"
            >
              {feature.included ? (
                <Check size={12} strokeWidth={2.5} className="mt-0.5 shrink-0 text-[#ea580c]" />
              ) : (
                <Minus
                  size={12}
                  strokeWidth={2}
                  className={`mt-0.5 shrink-0 ${
                    principle.highlighted ? "text-background/30" : "text-muted-foreground/40"
                  }`}
                />
              )}
              <span
                className={`text-xs font-mono leading-relaxed ${
                  feature.included
                    ? ""
                    : principle.highlighted
                      ? "text-background/30 line-through"
                      : "text-muted-foreground/40 line-through"
                }`}
              >
                {feature.text}
              </span>
            </motion.div>
          ))}
        </div>
      </div>

      <div className="px-5 pb-5 pt-3">
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
          className={`group w-full flex items-center justify-center gap-0 text-xs font-mono tracking-wider uppercase ${
            principle.highlighted
              ? "bg-background text-foreground"
              : "bg-foreground text-background"
          }`}
        >
          <span className="flex items-center justify-center w-9 h-9 bg-[#ea580c]">
            <ArrowRight size={14} strokeWidth={2} className="text-background" />
          </span>
          <span className="flex-1 py-2.5">{principle.cta}</span>
        </motion.button>
      </div>
    </motion.div>
  )
}

export function PricingSection() {
  return (
    <section className="w-full px-6 py-20 lg:px-12">
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        whileInView={{ opacity: 1, x: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5, ease }}
        className="flex items-center gap-4 mb-8"
      >
        <span className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground font-mono">
          {"// SECTION: DESIGN_PRINCIPLES"}
        </span>
        <div className="flex-1 border-t border-border" />
        <BlinkDot />
        <span className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground font-mono">006</span>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.6, ease }}
        className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 mb-12"
      >
        <div className="flex flex-col gap-3">
          <h2 className="text-2xl lg:text-3xl font-mono font-bold tracking-tight uppercase text-foreground text-balance">
            Principles, stack, and status
          </h2>
          <p className="text-xs lg:text-sm font-mono text-muted-foreground leading-relaxed max-w-xl">
            Simulation engine: Python + LangGraph. Backend: FastAPI. Frontend: Next.js. Data: yfinance, Reddit API, RSS news feeds, SEC EDGAR. Infra: Render + Cloudflare Pages.
          </p>
        </div>
        <StatusLine />
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-0">
        {PRINCIPLES.map((principle, i) => (
          <PrincipleCard key={principle.id} principle={principle} index={i} />
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ delay: 0.5, duration: 0.5, ease }}
        className="flex items-center gap-3 mt-6"
      >
        <span className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground font-mono">
          {"* Active development. MVP live at your URL here. Built by two students with $0 budget."}
        </span>
        <div className="flex-1 border-t border-border" />
      </motion.div>
    </section>
  )
}
