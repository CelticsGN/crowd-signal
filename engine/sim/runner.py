from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict
from engine.agents.persona import AgentState, PersonaType
from engine.memory.context import compute_memory_bias
from engine.memory.db import save_simulation_run
from engine.sim.narrator import generate_crowd_narrative
import logging
import random
import re

if TYPE_CHECKING:
    from engine.data.aggregator import MarketContext

# LLM-powered two-step parser (with compatibility float parser retained)
from engine.sim.llm_parser import parse_catalyst_analysis_llm

logger = logging.getLogger(__name__)


class CrowdState(TypedDict):
    ticker: str
    catalyst: str
    agents: list[AgentState]
    tick: int
    max_ticks: int


def _clamp_stance(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _influence_weight(persona: PersonaType) -> float:
    if persona is PersonaType.whale:
        return 0.8
    if persona in (PersonaType.retail_bull, PersonaType.retail_bear):
        return 0.2
    return 0.5


def _contrarian_strength(persona: PersonaType, nudge: float) -> float:
    if persona is PersonaType.retail_bear and nudge > 0.0:
        return 0.3
    if persona is PersonaType.retail_bull and nudge < 0.0:
        return 0.1
    if persona is PersonaType.whale:
        return 0.4
    return 0.0


def parse_catalyst_bias(catalyst: str) -> float:
    positive_keywords = ["beat", "surge", "growth", "bullish", "upgrade", "record"]
    negative_keywords = ["miss", "crash", "layoffs", "bearish", "downgrade", "loss"]

    text = catalyst.lower()

    pos_hits = sum(len(re.findall(rf"\b{re.escape(keyword)}\b", text)) for keyword in positive_keywords)
    neg_hits = sum(len(re.findall(rf"\b{re.escape(keyword)}\b", text)) for keyword in negative_keywords)

    if pos_hits == 0 and neg_hits == 0:
        return 0.0

    raw_bias = 0.30 * (pos_hits - neg_hits)

    pct_matches = [float(m) for m in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)]
    strength_multiplier = 1.0
    if pct_matches:
        strongest_pct = max(pct_matches)
        strength_multiplier += min(strongest_pct, 50.0) / 100.0

    return _clamp_stance(raw_bias * strength_multiplier)


def spawn_agents(n: int = 100, catalyst_bias: float = 0.0) -> list[AgentState]:
    personas = [
        PersonaType.retail_bull,
        PersonaType.retail_bear,
        PersonaType.whale,
        PersonaType.algo,
    ]
    bull_shift = max(-0.15, min(0.15, catalyst_bias * 0.30))
    persona_probs = [0.35 + bull_shift, 0.35 - bull_shift, 0.10, 0.20]

    agents: list[AgentState] = []
    for _ in range(n):
        persona = random.choices(personas, weights=persona_probs, k=1)[0]

        if persona is PersonaType.retail_bull:
            # Bulls are positively tilted, but still partially follow catalyst direction.
            seeded_stance = (0.85 * catalyst_bias + 0.15) + random.uniform(-0.18, 0.18)
            react_speed = random.uniform(0.10, 0.26)
        elif persona is PersonaType.retail_bear:
            # Bears are negatively tilted at neutral bias, but can still drift with strong catalysts.
            seeded_stance = (0.65 * catalyst_bias - 0.15) + random.uniform(-0.18, 0.18)
            react_speed = random.uniform(0.03, 0.12)
        elif persona is PersonaType.whale:
            seeded_stance = (0.80 * catalyst_bias) + random.uniform(-0.12, 0.12)
            react_speed = random.uniform(0.02, 0.10)
        else:
            seeded_stance = (0.90 * catalyst_bias) + random.uniform(-0.14, 0.14)
            react_speed = random.uniform(0.10, 0.25)

        agents.append(
            {
                "stance": _clamp_stance(seeded_stance),
                "persona": persona,
                "react_speed": react_speed,
                "confidence": random.uniform(0.4, 0.95),
            }
        )
    return agents


def tick_update(agents: list[AgentState], catalyst_bias: float) -> list[AgentState]:
    if not agents:
        return []

    majority_mean = sum(agent["stance"] for agent in agents) / len(agents)
    majority_sign = 0.0
    if majority_mean > 0:
        majority_sign = 1.0
    elif majority_mean < 0:
        majority_sign = -1.0

    updated: list[AgentState] = []
    bias_magnitude = abs(catalyst_bias)
    # Weak catalysts should create weaker crowd drift; strong catalysts can move faster.
    peer_scale = 0.35 + (bias_magnitude * 0.65)
    contrarian_scale = 0.35 + (bias_magnitude * 0.65)
    gravity_scale = 0.02 + (bias_magnitude * 0.06)

    for i, agent in enumerate(agents):
        neighbors = [a for j, a in enumerate(agents) if j != i]
        if not neighbors:
            updated.append(agent.copy())
            continue

        weight_sum = 0.0
        weighted_stance_sum = 0.0
        for neighbor in neighbors:
            w = _influence_weight(neighbor["persona"])
            weighted_stance_sum += w * neighbor["stance"]
            weight_sum += w

        target = weighted_stance_sum / weight_sum if weight_sum else 0.0

        if agent["persona"] is PersonaType.algo and majority_sign != 0.0:
            if target * majority_sign > 0:
                target *= 1.25

        nudge = (target - agent["stance"]) * agent["react_speed"] * peer_scale
        resistance = -nudge * _contrarian_strength(agent["persona"], nudge) * contrarian_scale
        final_nudge = nudge + resistance

        gravity = catalyst_bias * gravity_scale
        if agent["persona"] is PersonaType.whale:
            gravity *= 0.3
        elif agent["persona"] is PersonaType.algo:
            gravity *= 0.0

        new_stance = agent["stance"] + final_nudge + gravity
        updated.append(
            {
                "stance": _clamp_stance(new_stance),
                "persona": agent["persona"],
                "react_speed": agent["react_speed"],
                "confidence": agent["confidence"],
            }
        )

    return updated


def run_simulation(
    ticker: str,
    catalyst: str,
    horizon_minutes: int = 120,
    market_context: "MarketContext | None" = None,
) -> dict:
    """Run the crowd simulation and return aggregated results.

    If *market_context* is provided, the raw ``catalyst_bias`` derived
    from the catalyst text is further adjusted before agents are spawned:

    * ``volume_vs_avg > 1.5``          → bias amplified ×1.2
    * ``reddit_mentions > 50``         → bias magnitude +0.1
    * ``options_put_call_ratio > 1.5`` → nudge bearish (−0.1)
    * ``options_put_call_ratio < 0.5`` → nudge bullish (+0.1)

    All existing tick logic is unchanged.
    """
    catalyst_analysis = parse_catalyst_analysis_llm(catalyst)
    catalyst_bias = catalyst_analysis["final_bias"]

    # --- Market-context bias adjustments (only touches catalyst_bias) -
    if market_context is not None:
        # High volume amplifies the catalyst effect
        if (
            market_context.volume_vs_avg is not None
            and market_context.volume_vs_avg > 1.5
        ):
            catalyst_bias *= 1.2

        # High social activity → more volatile crowd
        if (
            market_context.reddit_mentions is not None
            and market_context.reddit_mentions > 50
        ):
            # Push in the direction already implied by the bias
            sign = 1.0 if catalyst_bias >= 0 else -1.0
            catalyst_bias += sign * 0.1

        # Smart-money options signal
        if market_context.options_put_call_ratio is not None:
            if market_context.options_put_call_ratio > 1.5:
                catalyst_bias -= 0.1  # heavy put buying → bearish tilt
            elif market_context.options_put_call_ratio < 0.5:
                catalyst_bias += 0.1  # heavy call buying → bullish tilt

        catalyst_bias = _clamp_stance(catalyst_bias)

    market_delta = catalyst_bias - catalyst_analysis["final_bias"]
    if abs(market_delta) > 1e-9:
        catalyst_analysis["market_adjustment"] += market_delta
        catalyst_analysis["final_bias"] = catalyst_bias
        catalyst_analysis["reasoning"].append(
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
        catalyst_analysis["market_adjustment"] += memory_delta
    for reason in memory_reasons:
        catalyst_analysis["reasoning"].append(
            {
                "rule": "memory_context_adjustment",
                "effect": "contextual_shift",
                "weight": memory_delta,
                "detail": reason,
            }
        )
    # ------------------------------------------------------------------

    spawned_agents = spawn_agents(catalyst_bias=catalyst_bias)
    initial_mean_stance = (
        sum(agent["stance"] for agent in spawned_agents) / len(spawned_agents)
        if spawned_agents
        else 0.0
    )

    state: CrowdState = {
        "ticker": ticker,
        "catalyst": catalyst,
        "agents": spawned_agents,
        "tick": 0,
        "max_ticks": max(1, min(48, horizon_minutes // 5)),
    }

    while state["tick"] < state["max_ticks"]:
        state["agents"] = tick_update(state["agents"], catalyst_bias=catalyst_bias)
        state["tick"] += 1

    agents = state["agents"]
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
        persona_stance_totals[persona_key] += agent["stance"]
        persona_confidence_totals[persona_key] += agent["confidence"]

        if agent["stance"] > probability_threshold:
            up_count += 1
        elif agent["stance"] < -probability_threshold:
            down_count += 1

        if agent["stance"] > 0.2:
            buckets["bullish"] += 1
        elif agent["stance"] < -0.2:
            buckets["bearish"] += 1
        else:
            buckets["neutral"] += 1

    mean_stance = sum(agent["stance"] for agent in agents) / total if total else 0.0
    probability_up = (up_count / total) if total else 0.0
    probability_down = (down_count / total) if total else 0.0

    logger.warning(
        "bias_diagnostics ticker=%s catalyst_bias=%.4f initial_mean_stance=%.4f final_mean_stance=%.4f probability_down=%.4f",
        ticker,
        catalyst_bias,
        initial_mean_stance,
        mean_stance,
        probability_down,
    )

    persona_mean_stance = {
        key: (persona_stance_totals[key] / persona_counts[key] if persona_counts[key] else 0.0)
        for key in persona_counts
    }
    persona_mean_confidence = {
        key: (persona_confidence_totals[key] / persona_counts[key] if persona_counts[key] else 0.0)
        for key in persona_counts
    }

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
        aggregate_stance=mean_stance,
        probability_up=probability_up,
        probability_down=probability_down,
        final_bias=float(catalyst_analysis.get("final_bias", catalyst_bias)),
        rules_fired=rules_fired,
    )

    crowd_narrative: list[dict] = []
    try:
        crowd_narrative = generate_crowd_narrative(
            ticker=ticker,
            catalyst=catalyst,
            simulation_result={
                "mean_stance": mean_stance,
                "probability_up": probability_up,
                "probability_down": probability_down,
                "persona_mean_stance": persona_mean_stance,
                "up_count": up_count,
                "down_count": down_count,
                "agent_count": total,
            },
            catalyst_analysis=catalyst_analysis,
        )
    except Exception:
        logger.exception("crowd_narrative_generation_failed ticker=%s", ticker)
        crowd_narrative = []

    return {
        "ticker": state["ticker"],
        "catalyst": state["catalyst"],
        "catalyst_analysis": catalyst_analysis,
        "ticks_run": state["tick"],
        "agent_count": total,
        "initial_mean_stance": initial_mean_stance,
        "mean_stance": mean_stance,
        "up_count": up_count,
        "down_count": down_count,
        "stance_buckets": buckets,
        "persona_counts": persona_counts,
        "persona_mean_stance": persona_mean_stance,
        "persona_mean_confidence": persona_mean_confidence,
        "crowd_narrative": crowd_narrative,
    }


if __name__ == "__main__":
    result = run_simulation(
        ticker="NVDA",
        catalyst="Earnings beat by 20%",
        horizon_minutes=120
    )
    print(result)
