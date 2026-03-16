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

export type CatalystExtraction = {
  primary_entity: string
  event_type: string
  magnitude: string
  direction: string
  related_entities: string[]
}

export type CatalystGraphNode =
  | string
  | {
      id: string
      kind?: string
      label?: string
      description?: string
    }

export type CatalystGraphEdge =
  | string
  | {
      source: string
      target: string
      relation?: string
      weight?: number
      adjustment?: number
      description?: string
    }

export type CatalystReasoningEntry = {
  rule: string
  description?: string
  detail?: string
  adjustment?: number
  weight?: number
  effect?: string
}

export type CatalystAnalysis = {
  extraction: CatalystExtraction
  graph_nodes: CatalystGraphNode[]
  graph_edges: CatalystGraphEdge[]
  reasoning: CatalystReasoningEntry[]
  final_bias: number
  market_scope: string
}

export type SimulateResponse = {
  ticker: string
  catalyst: string
  aggregate_stance: number
  probability_up: number
  probability_down: number
  personas: PersonaResult[]
  catalyst_analysis?: CatalystAnalysis | null
  memory_context?: Array<{
    catalyst: string
    probability_up: number
    direction: string
    created_at: string
  }> | null
}

export type StoredSimulationRun = {
  id: string
  createdAt: string
  result: SimulateResponse
}

export type RunSimulationResult = {
  runId: string
  result: SimulateResponse
}

type ProxyErrorShape = {
  error?: string
  details?: unknown
}

function stringifyDetails(details: unknown): string {
  if (typeof details === "string") return details
  if (details === null || details === undefined) return ""
  try {
    return JSON.stringify(details)
  } catch {
    return String(details)
  }
}

export function useSimulation() {
  const [data, setData] = useState<SimulateResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [analysisRunId, setAnalysisRunId] = useState<string | null>(null)

  const generateRunId = () => {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID()
    }
    return `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  }

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
        const errJson = json as ProxyErrorShape
        const message = errJson?.error ?? "Simulation request failed."
        const detailText = stringifyDetails(errJson?.details)
        const statusPrefix = `HTTP ${response.status}`
        throw new Error(detailText ? `${statusPrefix} - ${message}: ${detailText}` : `${statusPrefix} - ${message}`)
      }

      const result = json as SimulateResponse
      const runId = generateRunId()
      const storedRun: StoredSimulationRun = {
        id: runId,
        createdAt: new Date().toISOString(),
        result,
      }

      try {
        sessionStorage.setItem(`simulation_run_${runId}`, JSON.stringify(storedRun))
      } catch {
        // Ignore storage issues; simulation data is still returned in-memory.
      }

      setData(result)
      setAnalysisRunId(runId)
      return { runId, result } as RunSimulationResult
    } catch (err) {
      setData(null)
      setAnalysisRunId(null)
      setError(err instanceof Error ? err.message : "Unexpected simulation error.")
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  return { data, loading, error, analysisRunId, runSimulation }
}
