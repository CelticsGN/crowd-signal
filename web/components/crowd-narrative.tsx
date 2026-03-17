"use client"

import type { NarrativeEntry } from "@/hooks/useSimulation"

type CrowdNarrativeProps = {
  crowdNarrative?: NarrativeEntry[] | null
}

const PERSONA_STYLES: Record<string, { border: string; badge: string; stance: string; text: string }> = {
  retail_bull: {
    border: "border-orange-500/50",
    badge: "text-orange-400",
    stance: "text-orange-300",
    text: "text-orange-100",
  },
  retail_bear: {
    border: "border-blue-500/50",
    badge: "text-blue-400",
    stance: "text-blue-300",
    text: "text-blue-100",
  },
  whale: {
    border: "border-teal-500/50",
    badge: "text-teal-400",
    stance: "text-teal-300",
    text: "text-teal-100",
  },
  algo: {
    border: "border-purple-500/50",
    badge: "text-purple-400",
    stance: "text-purple-300",
    text: "text-purple-100",
  },
  narrator: {
    border: "border-zinc-500/60",
    badge: "text-zinc-200",
    stance: "text-zinc-300",
    text: "text-zinc-100",
  },
}

function formatPersonaLabel(persona: string): string {
  return persona.replaceAll("_", " ")
}

function formatStance(value: number): string {
  const sign = value >= 0 ? "+" : ""
  return `${sign}${value.toFixed(3)}`
}

export function CrowdNarrative({ crowdNarrative }: CrowdNarrativeProps) {
  if (!crowdNarrative || crowdNarrative.length === 0) return null

  return (
    <div className="space-y-3">
      {crowdNarrative.map((entry, index) => {
        const personaKey = entry.persona in PERSONA_STYLES ? entry.persona : "narrator"
        const palette = PERSONA_STYLES[personaKey]
        const isNarrator = entry.persona === "narrator"

        return (
          <article
            key={`${entry.agent_id}-${index}`}
            className={[
              "opacity-0 translate-y-2 border bg-black/50 p-4 font-mono",
              "[animation:reveal_420ms_ease-out_forwards]",
              isNarrator ? "w-full" : "w-full lg:w-[92%]",
              palette.border,
            ].join(" ")}
            style={{ animationDelay: `${index * 300}ms` }}
          >
            {isNarrator ? (
              <p className="mb-2 text-[10px] uppercase tracking-[0.22em] text-zinc-300">// CROWD_VERDICT</p>
            ) : null}

            <p className={`text-xs uppercase tracking-[0.18em] ${palette.badge}`}>{entry.agent_id}</p>
            <p className={`mt-1 text-[11px] uppercase tracking-[0.16em] ${palette.stance}`}>
              {formatPersonaLabel(entry.persona)} • stance {formatStance(entry.stance)}
            </p>
            <p className={`mt-3 leading-relaxed ${isNarrator ? "text-base" : "text-sm"} ${palette.text}`}>
              "{entry.message}"
            </p>
          </article>
        )
      })}

      <style jsx>{`
        @keyframes reveal {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  )
}
