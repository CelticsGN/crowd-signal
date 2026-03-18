from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, AsyncGenerator

from engine.agents.persona import PersonaType
from engine.memory.context import compute_memory_bias
from engine.memory.db import save_simulation_run
from engine.sim.llm_parser import parse_catalyst_analysis_llm
from engine.sim.narrator import generate_crowd_narrative
from engine.sim.runner import _clamp_stance, spawn_agents, tick_update

if TYPE_CHECKING:
    from engine.data.aggregator import MarketContext

logger = logging.getLogger(__name__)


def _summarize_agents(agents: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(agents)
    persona_counts = {persona.value: 0 for persona in PersonaType}
    persona_stance_totals = {persona.value: 0.0 for persona in PersonaType}
    persona_confidence_totals = {persona.value: 0.0 for persona in PersonaType}
    buckets = {"bullish": 0, "neutral": 0, "bearish": 0}
    up_count = 0
    down_count = 0

    probability_threshold = 0.25

    for agent in agents:
        persona_key = agent["persona"].value
        persona_counts[persona_key] += 1
        persona_stance_totals[persona_key] += float(agent["stance"])
        persona_confidence_totals[persona_key] += float(agent["confidence"])

        stance = float(agent["stance"])
        if stance > probability_threshold:
            up_count += 1
        elif stance < -probability_threshold:
            down_count += 1

        if stance > 0.2:
            buckets["bullish"] += 1
        elif stance < -0.2:
            buckets["bearish"] += 1
        else:
            buckets["neutral"] += 1

    mean_stance = sum(float(agent["stance"]) for agent in agents) / total if total else 0.0
    probability_up = (up_count / total) if total else 0.0
    probability_down = (down_count / total) if total else 0.0

    persona_mean_stance = {
        key: (persona_stance_totals[key] / persona_counts[key] if persona_counts[key] else 0.0)
        for key in persona_counts
    }
    persona_mean_confidence = {
        key: (persona_confidence_totals[key] / persona_counts[key] if persona_counts[key] else 0.0)
        for key in persona_counts
    }

    return {
        "agent_count": total,
        "up_count": up_count,
        "down_count": down_count,
        "mean_stance": mean_stance,
        "probability_up": probability_up,
        "probability_down": probability_down,
        "stance_buckets": buckets,
        "persona_counts": persona_counts,
        "persona_mean_stance": persona_mean_stance,
        "persona_mean_confidence": persona_mean_confidence,
    }


def _build_tick_thought(
    ticker: str,
    catalyst: str,
    tick: int,
    persona_mean_stance: dict[str, float],
) -> dict[str, Any]:
    thought_order = [
        ("retail_bull", "retail_bull_047"),
        ("retail_bear", "retail_bear_023"),
        ("whale", "whale_003"),
        ("algo", "algo_011"),
    ]
    persona, agent_id = thought_order[((tick // 5) - 1) % len(thought_order)]
    stance = float(persona_mean_stance.get(persona, 0.0))

    if stance > 0.1:
        message = (
            f"Tick {tick}: {persona} sees upside building on {ticker}; "
            f"catalyst still supports bullish positioning."
        )
    elif stance < -0.1:
        message = (
            f"Tick {tick}: {persona} is leaning defensive on {ticker}; "
            f"catalyst risk remains skewed to downside."
        )
    else:
        message = (
            f"Tick {tick}: {persona} remains balanced on {ticker}; "
            f"crowd still digesting catalyst signal."
        )

    return {
        "agent_id": agent_id,
        "persona": persona,
        "stance": stance,
        "message": message,
        "catalyst": catalyst,
    }


def _apply_market_adjustment(catalyst_bias: float, market_context: "MarketContext | None") -> float:
    if market_context is None:
        return catalyst_bias

    if market_context.volume_vs_avg is not None and market_context.volume_vs_avg > 1.5:
        catalyst_bias *= 1.2

    if market_context.reddit_mentions is not None and market_context.reddit_mentions > 50:
        sign = 1.0 if catalyst_bias >= 0 else -1.0
        catalyst_bias += sign * 0.1

    if market_context.options_put_call_ratio is not None:
        if market_context.options_put_call_ratio > 1.5:
            catalyst_bias -= 0.1
        elif market_context.options_put_call_ratio < 0.5:
            catalyst_bias += 0.1

    return _clamp_stance(catalyst_bias)


async def run_simulation_streaming(
    ticker: str,
    catalyst: str,
    horizon_minutes: int = 120,
    market_context: "MarketContext | None" = None,
) -> AsyncGenerator[dict[str, Any], None]:
    max_ticks = max(1, min(48, horizon_minutes // 5))

    yield {
        "type": "init",
        "ticker": ticker,
        "catalyst": catalyst,
        "horizon_minutes": horizon_minutes,
        "max_ticks": max_ticks,
        "agent_count": 100,
    }

    catalyst_analysis = parse_catalyst_analysis_llm(catalyst)
    catalyst_bias = float(catalyst_analysis.get("final_bias", 0.0))

    market_input_bias = catalyst_bias
    catalyst_bias = _apply_market_adjustment(catalyst_bias, market_context)
    market_delta = catalyst_bias - market_input_bias
    if abs(market_delta) > 1e-9:
        catalyst_analysis["market_adjustment"] = float(catalyst_analysis.get("market_adjustment", 0.0)) + market_delta
        catalyst_analysis["final_bias"] = catalyst_bias
        catalyst_analysis.setdefault("reasoning", []).append(
            {
                "rule": "market_context_adjustment",
                "effect": "contextual_shift",
                "weight": market_delta,
                "detail": "Live market context adjusted catalyst bias after extraction and graph synthesis.",
            }
        )

    memory_input_bias = catalyst_bias
    catalyst_bias, memory_reasons = compute_memory_bias(ticker, catalyst_bias)
    memory_delta = catalyst_bias - memory_input_bias
    if abs(memory_delta) > 1e-9:
        catalyst_analysis["final_bias"] = catalyst_bias
        catalyst_analysis["market_adjustment"] = float(catalyst_analysis.get("market_adjustment", 0.0)) + memory_delta
    for reason in memory_reasons:
        catalyst_analysis.setdefault("reasoning", []).append(
            {
                "rule": "memory_context_adjustment",
                "effect": "contextual_shift",
                "weight": memory_delta,
                "detail": reason,
            }
        )

    yield {
        "type": "catalyst_parsed",
        "analysis": catalyst_analysis,
        "final_bias": catalyst_bias,
    }

    agents = spawn_agents(catalyst_bias=catalyst_bias)
    initial_mean_stance = (sum(float(agent["stance"]) for agent in agents) / len(agents)) if agents else 0.0
    initial_summary = _summarize_agents(agents)

    yield {
        "type": "agents_spawned",
        "agent_count": initial_summary["agent_count"],
        "persona_counts": initial_summary["persona_counts"],
        "initial_mean_stance": initial_mean_stance,
    }

    thought_ticks = {5, 10, 15, 20}
    stream_thoughts: list[dict[str, Any]] = []
    herd_already_detected = False

    for tick in range(1, max_ticks + 1):
        agents = tick_update(agents, catalyst_bias=catalyst_bias)
        summary = _summarize_agents(agents)

        yield {
            "type": "tick",
            "tick": tick,
            "max_ticks": max_ticks,
            "mean_stance": summary["mean_stance"],
            "probability_up": summary["probability_up"],
            "probability_down": summary["probability_down"],
            "persona_mean_stance": summary["persona_mean_stance"],
            "up_count": summary["up_count"],
            "down_count": summary["down_count"],
            "agent_count": summary["agent_count"],
        }

        crowd_total = max(1, int(summary["agent_count"]))
        if not herd_already_detected and tick >= 5:
            if int(summary["up_count"]) > 70:
                yield {
                    "type": "herd_detected",
                    "tick": tick,
                    "direction": "bullish",
                    "strength": summary["up_count"] / crowd_total,
                }
                herd_already_detected = True
            elif int(summary["down_count"]) > 70:
                yield {
                    "type": "herd_detected",
                    "tick": tick,
                    "direction": "bearish",
                    "strength": summary["down_count"] / crowd_total,
                }
                herd_already_detected = True

        if tick in thought_ticks:
            thought = _build_tick_thought(
                ticker=ticker,
                catalyst=catalyst,
                tick=tick,
                persona_mean_stance=summary["persona_mean_stance"],
            )
            stream_thoughts.append(thought)
            yield {
                "type": "agent_thought",
                "tick": tick,
                **thought,
            }

        await asyncio.sleep(0)

    final_summary = _summarize_agents(agents)

    extraction = catalyst_analysis.get("extraction", {})
    rules_fired = [
        str(entry.get("rule", ""))
        for entry in catalyst_analysis.get("reasoning", [])
        if str(entry.get("rule", ""))
    ]

    save_simulation_run(
        ticker=ticker,
        catalyst=catalyst,
        catalyst_bias=catalyst_bias,
        event_type=str(extraction.get("event_type", "")),
        direction=str(extraction.get("direction", "")),
        magnitude=str(extraction.get("magnitude", "")),
        aggregate_stance=float(final_summary["mean_stance"]),
        probability_up=float(final_summary["probability_up"]),
        probability_down=float(final_summary["probability_down"]),
        final_bias=float(catalyst_analysis.get("final_bias", catalyst_bias)),
        rules_fired=rules_fired,
    )

    crowd_narrative: list[dict[str, Any]] = []
    narrator_entry: dict[str, Any] | None = None
    try:
        crowd_narrative = generate_crowd_narrative(
            ticker=ticker,
            catalyst=catalyst,
            simulation_result={
                "mean_stance": final_summary["mean_stance"],
                "probability_up": final_summary["probability_up"],
                "probability_down": final_summary["probability_down"],
                "persona_mean_stance": final_summary["persona_mean_stance"],
                "up_count": final_summary["up_count"],
                "down_count": final_summary["down_count"],
                "agent_count": final_summary["agent_count"],
            },
            catalyst_analysis=catalyst_analysis,
        )
        narrator_entry = next((entry for entry in crowd_narrative if entry.get("persona") == "narrator"), None)
    except Exception as exc:  # noqa: BLE001
        logger.error("[NARRATOR] narrator_groq_generation_failed ticker=%s error=%s", ticker, str(exc))
        crowd_narrative = []

    if narrator_entry is not None:
        yield {"type": "narrator", **narrator_entry}
    else:
        yield {
            "type": "narrator_error",
            "message": "Narrator generation failed - Groq unavailable",
            "agent_id": "narrator",
            "persona": "narrator",
        }

    merged_narrative = list(stream_thoughts)
    merged_narrative.extend([entry for entry in crowd_narrative if entry.get("persona") != "narrator"])
    if narrator_entry is not None:
        merged_narrative.append({
            "agent_id": narrator_entry.get("agent_id", "narrator"),
            "persona": narrator_entry.get("persona", "narrator"),
            "message": narrator_entry.get("message", ""),
            "stance": float(narrator_entry.get("stance", final_summary["mean_stance"])),
        })

    yield {
        "type": "complete",
        "result": {
            "ticker": ticker,
            "catalyst": catalyst,
            "horizon_minutes": horizon_minutes,
            "catalyst_analysis": catalyst_analysis,
            "ticks_run": max_ticks,
            "agent_count": final_summary["agent_count"],
            "initial_mean_stance": initial_mean_stance,
            "mean_stance": final_summary["mean_stance"],
            "up_count": final_summary["up_count"],
            "down_count": final_summary["down_count"],
            "stance_buckets": final_summary["stance_buckets"],
            "persona_counts": final_summary["persona_counts"],
            "persona_mean_stance": final_summary["persona_mean_stance"],
            "persona_mean_confidence": final_summary["persona_mean_confidence"],
            "crowd_narrative": merged_narrative,
            "market_context": market_context.model_dump() if market_context is not None else None,
        },
    }
