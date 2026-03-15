from __future__ import annotations

from typing import TypedDict
from engine.agents.persona import AgentState, PersonaType
import random
import re


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
            seeded_stance = (0.95 * catalyst_bias) + random.uniform(-0.20, 0.25)
            react_speed = random.uniform(0.10, 0.26)
        elif persona is PersonaType.retail_bear:
            seeded_stance = (-0.35 * catalyst_bias) + random.uniform(-0.55, 0.15)
            react_speed = random.uniform(0.03, 0.12)
        elif persona is PersonaType.whale:
            seeded_stance = (-0.30 * catalyst_bias) + random.uniform(-0.50, 0.20)
            react_speed = random.uniform(0.02, 0.10)
        else:
            seeded_stance = random.uniform(-0.15, 0.15)
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

        nudge = (target - agent["stance"]) * agent["react_speed"]
        resistance = -nudge * _contrarian_strength(agent["persona"], nudge)
        final_nudge = nudge + resistance

        gravity = catalyst_bias * 0.05
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


def run_simulation(ticker: str, catalyst: str, horizon_minutes: int = 120) -> dict:
    catalyst_bias = parse_catalyst_bias(catalyst)
    state: CrowdState = {
        "ticker": ticker,
        "catalyst": catalyst,
        "agents": spawn_agents(catalyst_bias=catalyst_bias),
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

    for agent in agents:
        persona_key = agent["persona"].value
        persona_counts[persona_key] += 1
        persona_stance_totals[persona_key] += agent["stance"]
        persona_confidence_totals[persona_key] += agent["confidence"]

        if agent["stance"] > 0.1:
            up_count += 1
        elif agent["stance"] < -0.1:
            down_count += 1

        if agent["stance"] > 0.2:
            buckets["bullish"] += 1
        elif agent["stance"] < -0.2:
            buckets["bearish"] += 1
        else:
            buckets["neutral"] += 1

    mean_stance = sum(agent["stance"] for agent in agents) / total if total else 0.0
    persona_mean_stance = {
        key: (persona_stance_totals[key] / persona_counts[key] if persona_counts[key] else 0.0)
        for key in persona_counts
    }
    persona_mean_confidence = {
        key: (persona_confidence_totals[key] / persona_counts[key] if persona_counts[key] else 0.0)
        for key in persona_counts
    }

    return {
        "ticker": state["ticker"],
        "catalyst": state["catalyst"],
        "ticks_run": state["tick"],
        "agent_count": total,
        "mean_stance": mean_stance,
        "up_count": up_count,
        "down_count": down_count,
        "stance_buckets": buckets,
        "persona_counts": persona_counts,
        "persona_mean_stance": persona_mean_stance,
        "persona_mean_confidence": persona_mean_confidence,
    }


if __name__ == "__main__":
    result = run_simulation(
        ticker="NVDA",
        catalyst="Earnings beat by 20%",
        horizon_minutes=120
    )
    print(result)
