"use client"

import { useCallback, useEffect, useRef, useState } from "react"

export type LiveChatEntry = {
  type: "system" | "chat_message" | "error"
  username?: string
  message: string
  timestamp: string
}

function resolveChatWsUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_WS_URL?.trim()
  if (explicit) return explicit

  if (typeof window !== "undefined") {
    const isLocalhost = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    if (isLocalhost) return "ws://127.0.0.1:8000"
  }

  return "wss://crowd-signal.onrender.com"
}

function nowIso(): string {
  return new Date().toISOString()
}

export function useLiveChat() {
  const socketRef = useRef<WebSocket | null>(null)
  const [messages, setMessages] = useState<LiveChatEntry[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [username, setUsername] = useState("")

  const connect = useCallback(
    (requestedUsername: string) => {
      const cleanUsername = requestedUsername.trim().slice(0, 24)
      if (!cleanUsername) return

      if (socketRef.current) {
        socketRef.current.close()
      }

      const socket = new WebSocket(`${resolveChatWsUrl().replace(/\/$/, "")}/ws/chat`)
      socketRef.current = socket

      socket.onopen = () => {
        setIsConnected(true)
        setUsername(cleanUsername)
        socket.send(JSON.stringify({ type: "join", username: cleanUsername }))
      }

      socket.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data) as Record<string, unknown>
          const type = String(parsed.type ?? "")
          if (type !== "system" && type !== "chat_message" && type !== "error") return

          setMessages((prev) => [
            ...prev,
            {
              type: type as LiveChatEntry["type"],
              username: typeof parsed.username === "string" ? parsed.username : undefined,
              message: String(parsed.message ?? ""),
              timestamp: typeof parsed.timestamp === "string" ? parsed.timestamp : nowIso(),
            },
          ])
        } catch {
          return
        }
      }

      socket.onclose = () => {
        setIsConnected(false)
      }

      socket.onerror = () => {
        setMessages((prev) => [
          ...prev,
          {
            type: "error",
            message: "Chat connection failed.",
            timestamp: nowIso(),
          },
        ])
      }
    },
    [],
  )

  const sendMessage = useCallback((text: string) => {
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) return
    const clean = text.trim()
    if (!clean) return
    socketRef.current.send(JSON.stringify({ type: "chat_message", message: clean }))
  }, [])

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.close()
      socketRef.current = null
    }
    setIsConnected(false)
  }, [])

  useEffect(() => () => disconnect(), [disconnect])

  return {
    messages,
    isConnected,
    username,
    connect,
    sendMessage,
    disconnect,
  }
}
