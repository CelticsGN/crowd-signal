"""Simulate route — POST /api/v1/simulate."""

from __future__ import annotations

from fastapi import APIRouter

from api.models.schemas import PersonaSentiment, SimulateRequest, SimulationResult
from engine.sim.runner import run_simulation

router = APIRouter()

_PERSONAS = ["retail_bull", "retail_bear", "whale", "algo"]


@router.post("/simulate", response_model=SimulationResult)
async def simulate(request: SimulateRequest) -> SimulationResult:
    """Run a crowd simulation for the given ticker and catalyst.

    Args:
        request: Validated :class:`SimulateRequest` payload.

    Returns:
        A :class:`SimulationResult` with per-persona breakdowns and
        aggregate directional probabilities.
    """
    sim_result = run_simulation(
        ticker=request.ticker.upper(),
        catalyst=request.catalyst,
        horizon_minutes=request.horizon_minutes,
    )

    total_agents = int(sim_result.get("agent_count", 0))
    bullish_count = int(sim_result.get("up_count", 0))
    bearish_count = int(sim_result.get("down_count", 0))

    if total_agents > 0:
        probability_up = bullish_count / total_agents
        probability_down = bearish_count / total_agents
    else:
        probability_up = 0.0
        probability_down = 0.0

    persona_counts = sim_result.get("persona_counts", {})
    persona_mean_stance = sim_result.get("persona_mean_stance", {})
    persona_mean_confidence = sim_result.get("persona_mean_confidence", {})

    personas: list[PersonaSentiment] = []
    for persona in _PERSONAS:
        stance = float(persona_mean_stance.get(persona, 0.0))
        count = int(persona_counts.get(persona, 0))
        weight = (count / total_agents) if total_agents > 0 else 0.0
        confidence = float(persona_mean_confidence.get(persona, 0.0))
        personas.append(
            PersonaSentiment(
                persona=persona,
                stance=stance,
                confidence=confidence,
                weight=weight,
            )
        )

    return SimulationResult(
        ticker=request.ticker.upper(),
        catalyst=request.catalyst,
        horizon_minutes=request.horizon_minutes,
        aggregate_stance=float(sim_result.get("mean_stance", 0.0)),
        probability_up=probability_up,
        probability_down=probability_down,
        personas=personas,
    )
