"use client"

import { motion } from "framer-motion"
import { VerdictResponse } from "@/hooks/useSimulation"

type VerdictCardProps = {
  verdict: VerdictResponse
}

export function VerdictCard({ verdict }: VerdictCardProps) {
  const {
    action,
    confidence,
    reasoning,
    entry_price,
    target_price,
    stop_price,
    range_low,
    range_high,
  } = verdict

  const isBuy = action === "BUY"
  const isSell = action === "SELL"
  
  // Tailwind color classes for the action text and optional left border
  const actionColor = isBuy 
    ? "text-emerald-500" 
    : isSell 
      ? "text-rose-500" 
      : "text-muted-foreground"
      
  const borderColor = isBuy
    ? "border-l-emerald-500"
    : isSell
      ? "border-l-rose-500"
      : "border-l-foreground/20"

  return (
    <motion.section
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className={`w-full border border-foreground/20 bg-background/80 p-5 ${borderColor} border-l-4`}
    >
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div>
          <p className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground mb-1">
            // VERDICT_OUTPUT
          </p>
          <div className="flex items-baseline gap-3">
            <h2 className={`text-4xl font-semibold tracking-tight ${actionColor}`}>
              {action}
            </h2>
            {confidence !== undefined && confidence !== null && (
              <span className="text-sm font-mono tracking-[0.16em] text-muted-foreground uppercase">
                {confidence}% CONV
              </span>
            )}
          </div>
          <p className="mt-4 text-sm text-foreground max-w-2xl font-medium">
            {reasoning}
          </p>
        </div>
        
        <div className="flex flex-col gap-2 min-w-[200px] border-t border-foreground/10 md:border-t-0 md:border-l md:pl-5 pt-3 md:pt-0">
          <p className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground mb-1">
            // PARAMETERS
          </p>
          {(isBuy || isSell) ? (
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono tracking-[0.16em]">
                <span className="text-muted-foreground">ENTRY</span>
                <span className="text-foreground">{entry_price ? entry_price.toFixed(2) : "MKT"}</span>
              </div>
              <div className="flex justify-between text-xs font-mono tracking-[0.16em]">
                <span className="text-muted-foreground">TARGET</span>
                <span className="text-foreground">{target_price ? target_price.toFixed(2) : "—"}</span>
              </div>
              <div className="flex justify-between text-xs font-mono tracking-[0.16em]">
                <span className="text-muted-foreground">STOP</span>
                <span className="text-foreground">{stop_price ? stop_price.toFixed(2) : "—"}</span>
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono tracking-[0.16em]">
                <span className="text-muted-foreground">RANGE LOW</span>
                <span className="text-foreground">{range_low ? range_low.toFixed(2) : "—"}</span>
              </div>
              <div className="flex justify-between text-xs font-mono tracking-[0.16em]">
                <span className="text-muted-foreground">RANGE HIGH</span>
                <span className="text-foreground">{range_high ? range_high.toFixed(2) : "—"}</span>
              </div>
            </div>
          )}
        </div>
      </div>
      
      <div className="mt-5 pt-4 border-t border-foreground/10">
        <p className="text-[10px] tracking-wide text-muted-foreground/70 uppercase">
          This is an AI-generated simulation, not financial advice. Past accuracy does not guarantee future results.
        </p>
      </div>
    </motion.section>
  )
}
