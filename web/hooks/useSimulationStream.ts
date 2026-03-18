"use client"

import { useCallback, useMemo, useRef, useState } from "react"
import type { SimulateRequest, SimulateResponse, StoredSimulationRun } from "@/hooks/useSimulation"

export type SimulationStreamEvent = {
  type: string
  [key: string]: unknown
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

function generateRunId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }
  return `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

function resolveWsUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_WS_URL?.trim()
  if (explicit) return explicit

  if (typeof window !== "undefined") {
    const isLocalhost = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    if (isLocalhost) {
      return "ws://127.0.0.1:8000"
    }
  }

  return "wss://crowd-signal.onrender.com"
}

export function useSimulationStream() {
  const socketRef = useRef<WebSocket | null>(null)
  const hasCompletedRef = useRef(false)
  const fallbackStartedRef = useRef(false)

  const [events, setEvents] = useState<SimulationStreamEvent[]>([])
  const [currentTick, setCurrentTick] = useState(0)
  const [maxTicks, setMaxTicks] = useState(0)
  const [isConnected, setIsConnected] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [isComplete, setIsComplete] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [finalResult, setFinalResult] = useState<SimulateResponse | null>(null)
  const [analysisRunId, setAnalysisRunId] = useState<string | null>(null)

  const agentThoughts = useMemo(
    () => events.filter((entry) => entry.type === "agent_thought"),
    [events],
  )

  const persistResult = useCallback((result: SimulateResponse): string => {
    const runId = generateRunId()
    const storedRun: StoredSimulationRun = {
      id: runId,
      createdAt: new Date().toISOString(),
      result,
    }

    try {
      sessionStorage.setItem(`simulation_run_${runId}`, JSON.stringify(storedRun))
    } catch {
      // Ignore storage issues and continue with in-memory result.
    }

    setAnalysisRunId(runId)
    return runId
  }, [])

  const runFallback = useCallback(async (payload: SimulateRequest) => {
    if (fallbackStartedRef.current) {
      return
    }
    fallbackStartedRef.current = true

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
      persistResult(result)
      setFinalResult(result)
      setIsComplete(true)
      setIsStreaming(false)
      setEvents((prev) => [
        ...prev,
        {
          type: "complete",
          result,
          source: "fallback_post",
        },
      ])
    } catch (fallbackError) {
      setError(fallbackError instanceof Error ? fallbackError.message : "Unexpected fallback simulation error.")
      setIsStreaming(false)
    }
  }, [persistResult])

  const startSimulation = useCallback(async (payload: SimulateRequest) => {
    if (socketRef.current) {
      socketRef.current.close()
      socketRef.current = null
    }

    setEvents([])
    setCurrentTick(0)
    setMaxTicks(0)
    setIsConnected(false)
    setIsStreaming(true)
    setIsComplete(false)
    setError(null)
    setFinalResult(null)
    setAnalysisRunId(null)

    hasCompletedRef.current = false
    fallbackStartedRef.current = false

    const wsBase = resolveWsUrl().replace(/\/$/, "")
    const socket = new WebSocket(`${wsBase}/ws/simulate`)
    socketRef.current = socket

    socket.onopen = () => {
      setIsConnected(true)
      socket.send(JSON.stringify(payload))
    }

    socket.onmessage = (event) => {
      let parsed: SimulationStreamEvent
      try {
        parsed = JSON.parse(event.data) as SimulationStreamEvent
      } catch {
        return
      }

      if (parsed.type === "ping") {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: "pong" }))
        }
        return
      }

      setEvents((prev) => [...prev, parsed])

      if (parsed.type === "tick") {
        const tick = Number(parsed.tick ?? 0)
        const total = Number(parsed.max_ticks ?? 0)
        setCurrentTick(tick)
        if (total > 0) {
          setMaxTicks(total)
        }
      }

      if (parsed.type === "init") {
        const total = Number(parsed.max_ticks ?? 0)
        if (total > 0) {
          setMaxTicks(total)
        }
      }

      if (parsed.type === "error") {
        const message = typeof parsed.message === "string" ? parsed.message : "Simulation stream failed."
        setError(message)
      }

      if (parsed.type === "complete") {
        const result = (parsed.result ?? null) as SimulateResponse | null
        if (result) {
          hasCompletedRef.current = true
          persistResult(result)
          setFinalResult(result)
          setIsComplete(true)
        }
        setIsStreaming(false)
      }
    }

    socket.onerror = (event) => {
      console.error("[WS] Connection failed:", event)
      console.error("[WS] Falling back to POST endpoint")
      if (!hasCompletedRef.current) {
        runFallback(payload)
      }
    }

    socket.onclose = () => {
      setIsConnected(false)
      if (!hasCompletedRef.current) {
        console.error("[WS] Falling back to POST endpoint")
        runFallback(payload)
      }
    }
  }, [persistResult, runFallback])

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.close()
      socketRef.current = null
    }
    setIsConnected(false)
    setIsStreaming(false)
  }, [])

  return {
    events,
    currentTick,
    maxTicks,
    agentThoughts,
    isConnected,
    isStreaming,
    isComplete,
    error,
    finalResult,
    analysisRunId,
    startSimulation,
    disconnect,
  }
}
