"use client"

import { useCallback, useState } from "react"

export type SimulateRequest = {
  ticker: string
  catalyst: string
  horizon_minutes: number
}

export type PersonaResult = {
  persona: string
  stance: number
  confidence: number
  weight: number
}

export type SimulateResponse = {
  ticker: string
  catalyst: string
  aggregate_stance: number
  probability_up: number
  probability_down: number
  personas: PersonaResult[]
}

type ProxyErrorShape = {
  error?: string
  details?: unknown
}

export function useSimulation() {
  const [data, setData] = useState<SimulateResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runSimulation = useCallback(async (payload: SimulateRequest) => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch("/api/simulate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      })

      const json = (await response.json()) as SimulateResponse | ProxyErrorShape

      if (!response.ok) {
        const message = (json as ProxyErrorShape)?.error ?? "Simulation request failed."
        throw new Error(message)
      }

      setData(json as SimulateResponse)
    } catch (err) {
      setData(null)
      setError(err instanceof Error ? err.message : "Unexpected simulation error.")
    } finally {
      setLoading(false)
    }
  }, [])

  return { data, loading, error, runSimulation }
}
