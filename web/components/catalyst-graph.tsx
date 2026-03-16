"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import * as d3 from "d3"
import type { CatalystAnalysis } from "@/hooks/useSimulation"

type Props = {
  analysis: CatalystAnalysis
  height?: number
  mode?: "compact" | "analysis"
  showCounts?: boolean
}

type GraphNode = {
  id: string
  label: string
  kind: "primary" | "event" | "related" | "outcome"
  description: string
}

type GraphEdge = {
  source: string
  target: string
  relation: string
  weight: number
}

type TooltipState = {
  x: number
  y: number
  text: string
}

function nodeColor(kind: GraphNode["kind"], finalBias: number): string {
  if (kind === "primary") return "#f59e0b"
  if (kind === "event") return "#a855f7"
  if (kind === "related") return "#2dd4bf"
  if (finalBias > 0.1) return "#22c55e"
  if (finalBias < -0.1) return "#ef4444"
  return "#9ca3af"
}

function parseEdgeString(raw: string): GraphEdge | null {
  const cleaned = raw.trim()
  const arrow = cleaned.match(/^(.+?)\s*->\s*(.+)$/)
  if (!arrow) return null
  return {
    source: arrow[1].trim(),
    target: arrow[2].trim(),
    relation: "linked",
    weight: 0.12,
  }
}

function makeNodeDescription(node: GraphNode, analysis: CatalystAnalysis): string {
  if (node.kind === "primary") return `Primary entity: ${analysis.extraction.primary_entity}`
  if (node.kind === "event") {
    return `Event: ${analysis.extraction.event_type} | Direction: ${analysis.extraction.direction} | Magnitude: ${analysis.extraction.magnitude}`
  }
  if (node.kind === "related") return `Related entity: ${node.label}`
  return `Bias outcome: ${node.label} (final_bias ${analysis.final_bias.toFixed(3)})`
}

function normalizeGraph(analysis: CatalystAnalysis): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const nodesMap = new Map<string, GraphNode>()

  const primaryId = analysis.extraction.primary_entity || "entity"
  const eventId = `event:${analysis.extraction.event_type}`
  const outcomeLabel = analysis.final_bias > 0.1 ? "BULLISH" : analysis.final_bias < -0.1 ? "BEARISH" : "NEUTRAL"
  const outcomeId = `bias:${outcomeLabel}`

  const upsertNode = (node: GraphNode) => {
    if (!nodesMap.has(node.id)) nodesMap.set(node.id, node)
  }

  const inferKind = (id: string, rawType?: string, rawKind?: string): GraphNode["kind"] => {
    const t = (rawType || rawKind || "").toLowerCase()
    if (t === "related" || t === "related_entity") return "related"
    if (t === "event") return "event"
    if (t === "primary" || t === "entity") return "primary"
    if (t === "outcome" || id.startsWith("bias:")) return "outcome"
    if (id === primaryId) return "primary"
    if (id === eventId) return "event"
    if (id === outcomeId) return "outcome"
    return "related"
  }

  // Source-of-truth: render every backend graph node first.
  for (const rawNode of analysis.graph_nodes ?? []) {
    if (typeof rawNode === "string") {
      upsertNode({
        id: rawNode,
        label: rawNode.replace(/^event:/, "").replace(/^bias:/, "").replace(/_/g, " ").toUpperCase(),
        kind: inferKind(rawNode),
        description: "",
      })
      continue
    }

    const id = rawNode.id || "unknown"
    const kind = inferKind(id, (rawNode as any).type, (rawNode as any).kind)

    upsertNode({
      id,
      label: (rawNode.label || id).replace(/^event:/, "").replace(/^bias:/, "").replace(/_/g, " ").toUpperCase(),
      kind,
      description: rawNode.description || "",
    })
  }

  // Backfill critical nodes if backend graph payload is sparse.
  upsertNode({
    id: primaryId,
    label: primaryId,
    kind: "primary",
    description: "",
  })
  upsertNode({
    id: eventId,
    label: analysis.extraction.event_type.toUpperCase(),
    kind: "event",
    description: "",
  })
  for (const related of analysis.extraction.related_entities ?? []) {
    upsertNode({
      id: related,
      label: related.replace(/_/g, " ").toUpperCase(),
      kind: "related",
      description: "",
    })
  }
  upsertNode({
    id: outcomeId,
    label: outcomeLabel,
    kind: "outcome",
    description: "",
  })

  const edges: GraphEdge[] = []
  const edgeKeys = new Set<string>()
  const pushEdge = (edge: GraphEdge) => {
    const key = `${edge.source}->${edge.target}:${edge.relation}`
    if (edgeKeys.has(key)) return
    edgeKeys.add(key)
    edges.push(edge)
  }

  pushEdge({ source: primaryId, target: eventId, relation: "has_event", weight: 0.18 })
  for (const related of analysis.extraction.related_entities ?? []) {
    pushEdge({ source: eventId, target: related, relation: "related_to", weight: 0.12 })
  }
  pushEdge({ source: eventId, target: outcomeId, relation: "bias_outcome", weight: Math.max(0.12, Math.abs(analysis.final_bias)) })

  for (const rawEdge of analysis.graph_edges ?? []) {
    if (typeof rawEdge === "string") {
      const parsed = parseEdgeString(rawEdge)
      if (parsed) pushEdge(parsed)
      continue
    }
    pushEdge({
      source: rawEdge.source,
      target: rawEdge.target,
      relation: rawEdge.relation || "linked",
      weight: Math.abs(rawEdge.weight ?? rawEdge.adjustment ?? 0.12),
    })
  }

  // Ensure nodes referenced by edges are always present/rendered.
  for (const edge of edges) {
    if (!nodesMap.has(edge.source)) {
      upsertNode({
        id: edge.source,
        label: edge.source.replace(/^event:/, "").replace(/^bias:/, "").replace(/_/g, " ").toUpperCase(),
        kind: inferKind(edge.source),
        description: "",
      })
    }
    if (!nodesMap.has(edge.target)) {
      upsertNode({
        id: edge.target,
        label: edge.target.replace(/^event:/, "").replace(/^bias:/, "").replace(/_/g, " ").toUpperCase(),
        kind: inferKind(edge.target),
        description: "",
      })
    }
  }

  const nodes = [...nodesMap.values()].map((node) => ({
    ...node,
    description: node.description || makeNodeDescription(node, analysis),
  }))

  return { nodes, edges }
}

export function CatalystGraph({ analysis, height = 320, mode = "compact", showCounts = true }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const svgRef = useRef<SVGSVGElement | null>(null)
  const [width, setWidth] = useState(800)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  const { nodes, edges } = useMemo(() => normalizeGraph(analysis), [analysis])

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const observer = new ResizeObserver((entries) => {
      const nextWidth = entries[0]?.contentRect.width
      if (nextWidth) setWidth(nextWidth)
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const svgEl = svgRef.current
    if (!svgEl) return

    const svg = d3.select(svgEl)
    svg.selectAll("*").remove()

    svg.attr("viewBox", `0 0 ${width} ${height}`)

    const marker = svg
      .append("defs")
      .append("marker")
      .attr("id", "graph-arrow")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 22)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")

    marker
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", "#94a3b8")

    const graphNodes = nodes.map((n) => ({ ...n })) as Array<GraphNode & d3.SimulationNodeDatum>
    const graphLinks = edges.map((e) => ({ ...e })) as Array<GraphEdge & d3.SimulationLinkDatum<GraphNode & d3.SimulationNodeDatum>>

    const relatedNodes = graphNodes.filter((n) => n.kind === "related")

    // Deterministic initial placement avoids first-frame overlap at graph center.
    for (const n of graphNodes) {
      if (n.kind === "primary") {
        n.x = width / 2
        n.y = height / 2
        continue
      }

      if (n.kind === "event") {
        n.x = width / 2
        n.y = height / 3
        continue
      }

      if (n.kind === "outcome") {
        n.x = width * 0.35
        n.y = height * 0.72
        continue
      }

      const relatedIndex = relatedNodes.findIndex((related) => related.id === n.id)
      if (relatedIndex === 0) {
        n.x = width * 0.7
        n.y = height * 0.3
      } else if (relatedIndex === 1) {
        n.x = width * 0.7
        n.y = height * 0.6
      } else if (relatedIndex === 2) {
        n.x = width * 0.8
        n.y = height * 0.45
      } else {
        const arcIndex = Math.max(0, relatedIndex)
        const angle = (-Math.PI / 3) + (arcIndex * (Math.PI / 8))
        const arcRadius = mode === "analysis" ? 88 : 52
        n.x = width * 0.76 + Math.cos(angle) * arcRadius
        n.y = height * 0.46 + Math.sin(angle) * arcRadius
      }
    }

    const linkNodeId = (value: string | GraphNode | (GraphNode & d3.SimulationNodeDatum)) =>
      typeof value === "string" ? value : value.id

    const eventRelatedDistance = mode === "analysis" ? 160 : 120
    const otherDistance = mode === "analysis" ? 110 : 80
    const relatedCharge = mode === "analysis" ? -520 : -400
    const otherCharge = mode === "analysis" ? -420 : -300
    const collisionRadius = mode === "analysis" ? 34 : 25

    const simulation = d3
      .forceSimulation(graphNodes)
      .force(
        "link",
        d3
          .forceLink(graphLinks)
          .id((d: any) => d.id)
          .distance((link) => {
            const sourceId = linkNodeId(link.source as any)
            const targetId = linkNodeId(link.target as any)
            const sourceKind = graphNodes.find((node) => node.id === sourceId)?.kind
            const targetKind = graphNodes.find((node) => node.id === targetId)?.kind
            if (sourceKind === "event" && targetKind === "related") return eventRelatedDistance
            return otherDistance
          })
          .strength(0.45),
      )
          .force("charge", d3.forceManyBody<GraphNode & d3.SimulationNodeDatum>().strength((d) => (d.kind === "related" ? relatedCharge : otherCharge)))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("x", d3.forceX(width / 2).strength(0.05))
      .force("y", d3.forceY(height / 2).strength(0.05))
          .force("collision", d3.forceCollide().radius(collisionRadius))

    const isConnected = (edge: GraphEdge, nodeId: string | null) => {
      if (!nodeId) return true
      return edge.source === nodeId || edge.target === nodeId
    }

    const linkGroup = svg.append("g").attr("stroke-linecap", "round")

    const links = linkGroup
      .selectAll("line")
      .data(graphLinks)
      .enter()
      .append("line")
      .attr("stroke", (d) => (isConnected(d, selectedNode) ? "#cbd5e1" : "#475569"))
      .attr("stroke-opacity", (d) => (isConnected(d, selectedNode) ? 0.85 : 0.2))
      .attr("stroke-width", (d) => 1 + Math.min(6, Math.abs(d.weight) * 10))
      .attr("marker-end", "url(#graph-arrow)")

    links
      .transition()
      .duration(450)
      .attr("stroke-opacity", 0.2)
      .transition()
      .duration(700)
      .attr("stroke-opacity", (d) => (isConnected(d, selectedNode) ? 0.85 : 0.2))

    const nodeGroup = svg.append("g")

    const drag = d3
      .drag<SVGGElement, GraphNode & d3.SimulationNodeDatum>()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      })
      .on("drag", (event, d) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null
        d.fy = null
      })

    const node = nodeGroup
      .selectAll("g")
      .data(graphNodes)
      .enter()
      .append("g")
      .style("cursor", "pointer")
      .call(drag)
      .on("mouseenter", (event, d) => {
        setTooltip({ x: event.offsetX + 12, y: event.offsetY + 12, text: d.description })
      })
      .on("mousemove", (event, d) => {
        setTooltip({ x: event.offsetX + 12, y: event.offsetY + 12, text: d.description })
      })
      .on("mouseleave", () => setTooltip(null))
      .on("click", (_, d) => {
        setSelectedNode((current) => (current === d.id ? null : d.id))
      })

    node
      .append("circle")
      .attr("r", (d) => {
        if (mode === "analysis") return d.kind === "related" ? 12 : 16
        return d.kind === "related" ? 10 : 14
      })
      .attr("fill", (d) => nodeColor(d.kind, analysis.final_bias))
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 1)

    node
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", mode === "analysis" ? 34 : 30)
      .attr("font-size", mode === "analysis" ? 12 : 9)
      .attr("fill", "#a0a0a0")
      .attr("font-family", "var(--font-mono), monospace")
      .text((d) => (d.kind === "related" ? d.id.replace(/_/g, " ").toUpperCase() : d.label))

    simulation.on("tick", () => {
      links
        .attr("x1", (d: any) => d.source.x ?? 0)
        .attr("y1", (d: any) => d.source.y ?? 0)
        .attr("x2", (d: any) => d.target.x ?? 0)
        .attr("y2", (d: any) => d.target.y ?? 0)

      node.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`)
    })

    return () => {
      simulation.stop()
    }
  }, [analysis.final_bias, edges, height, mode, nodes, selectedNode, width])

  const biasTone = analysis.final_bias > 0.1 ? "text-green-400" : analysis.final_bias < -0.1 ? "text-red-400" : "text-zinc-400"
  const graphCounts = `${nodes.length} nodes  •  ${edges.length} edges`

  return (
    <section className="border border-foreground/20 bg-background/60 p-4 lg:p-5">
      <div className="flex flex-col items-center justify-center mb-4">
        <p className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">FINAL_BIAS</p>
        <p className={`${mode === "analysis" ? "text-5xl" : "text-3xl"} font-bold font-mono ${biasTone}`}>{analysis.final_bias.toFixed(3)}</p>
        <p className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">{analysis.market_scope}</p>
      </div>

      <div
        ref={containerRef}
        className="relative w-full border border-foreground/20 bg-foreground/5 dark:bg-black/20 overflow-hidden"
        style={{ height }}
      >
        {nodes.length < 2 ? (
          <div className="h-full w-full flex items-center justify-center text-xs font-mono tracking-[0.16em] uppercase text-muted-foreground">
            // GRAPH_UNAVAILABLE - insufficient entity data
          </div>
        ) : (
          <svg ref={svgRef} className="w-full h-full" role="img" aria-label="Catalyst knowledge graph visualization" />
        )}

        {showCounts ? (
          <div className="absolute right-2 top-2 text-[10px] font-mono tracking-[0.12em] uppercase text-muted-foreground bg-background/70 px-2 py-1 border border-foreground/20">
            {graphCounts}
          </div>
        ) : null}

        {tooltip ? (
          <div
            className="pointer-events-none absolute z-20 max-w-[260px] border border-foreground/30 bg-background/95 dark:bg-black/90 px-2 py-1 text-[10px] text-foreground font-mono"
            style={{ left: tooltip.x, top: tooltip.y }}
          >
            {tooltip.text}
          </div>
        ) : null}
      </div>
    </section>
  )
}
