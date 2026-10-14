"use client"

import { FormEvent, useEffect, useMemo, useRef, useState } from "react"
import { motion } from "framer-motion"
import { useLiveChat } from "@/hooks/useLiveChat"

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return ""
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

export function LiveChatPanel() {
  const [pendingUsername, setPendingUsername] = useState("")
  const [pendingMessage, setPendingMessage] = useState("")
  const { messages, isConnected, username, connect, sendMessage, disconnect } = useLiveChat()
  const scrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const connectionLabel = useMemo(() => (isConnected ? "chat_connected" : "chat_disconnected"), [isConnected])

  const onJoin = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    connect(pendingUsername)
  }

  const onSend = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    sendMessage(pendingMessage)
    setPendingMessage("")
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="w-full border border-foreground/20 bg-background/80 backdrop-blur-sm p-4 lg:p-6"
    >
      <div className="flex items-center gap-4 mb-4">
        <span className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">{"// LIVE_CHAT"}</span>
        <div className="flex-1 border-t border-border" />
        <span className={`text-[10px] font-mono uppercase tracking-[0.16em] ${isConnected ? "text-emerald-400" : "text-amber-400"}`}>
          {connectionLabel}
        </span>
      </div>

      {!isConnected ? (
        <form onSubmit={onJoin} className="flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            required
            value={pendingUsername}
            onChange={(event) => setPendingUsername(event.target.value)}
            placeholder="Enter display name"
            className="border border-foreground/25 bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/70 outline-none focus:border-foreground"
            maxLength={24}
          />
          <button type="submit" className="bg-foreground text-background px-5 py-2 text-xs font-mono tracking-widest uppercase">
            Join Chat
          </button>
        </form>
      ) : (
        <div className="mb-3 flex items-center justify-between">
          <p className="text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">Signed in as {username}</p>
          <button
            type="button"
            onClick={disconnect}
            className="border border-foreground/20 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.14em] text-muted-foreground hover:text-foreground"
          >
            Disconnect
          </button>
        </div>
      )}

      <div ref={scrollRef} className="max-h-72 overflow-y-auto border border-foreground/20 bg-background/70 p-3 space-y-2 mt-4">
        {messages.length === 0 ? (
          <p className="text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">No messages yet.</p>
        ) : null}

        {messages.map((entry, index) => (
          <div key={`${entry.timestamp}_${index}`} className="text-xs font-mono leading-relaxed">
            <span className="mr-2 text-muted-foreground">{formatTimestamp(entry.timestamp)}</span>
            {entry.type === "chat_message" ? (
              <>
                <span className="mr-2 text-cyan-300">[{entry.username ?? "anon"}]</span>
                <span className="text-foreground/90">{entry.message}</span>
              </>
            ) : (
              <span className={entry.type === "error" ? "text-destructive" : "text-lime-300"}>{entry.message}</span>
            )}
          </div>
        ))}
      </div>

      <form onSubmit={onSend} className="mt-4 flex flex-col gap-3 sm:flex-row">
        <input
          type="text"
          value={pendingMessage}
          onChange={(event) => setPendingMessage(event.target.value)}
          placeholder={isConnected ? "Type a message..." : "Join chat to send messages"}
          disabled={!isConnected}
          maxLength={500}
          className="flex-1 border border-foreground/25 bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/70 outline-none focus:border-foreground disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={!isConnected || !pendingMessage.trim()}
          className="bg-foreground text-background px-5 py-2 text-xs font-mono tracking-widest uppercase disabled:opacity-60"
        >
          Send
        </button>
      </form>
    </motion.section>
  )
}
