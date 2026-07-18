"""Simulate route — POST /api/v1/simulate."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from api.models.schemas import PersonaSentiment, SimulateRequest, SimulationResult, VerdictResponse
from engine.memory.db import get_recent_runs, update_verdict_on_latest_run
from engine.data.aggregator import MarketDataAggregator
from engine.sim.runner import run_simulation
from engine.sim.verdict import blend_probabilities, compute_verdict

router = APIRouter()
logger = logging.getLogger(__name__)

_PERSONAS = ["retail_bull", "retail_bear", "whale", "algo"]


@router.post("/simulate", response_model=SimulationResult)
async def simulate(request: SimulateRequest) -> SimulationResult:
    """Run a crowd simulation for the given ticker and catalyst.

    Fetches live market context (price, volume, options) before
    running the simulation so the engine can adjust the catalyst bias
    based on real-world signals. If the context fetch fails for any
    reason the simulation still runs without market enrichment.

    Args:
        request: Validated :class:`SimulateRequest` payload.

    Returns:
        A :class:`SimulationResult` with per-persona breakdowns,
        aggregate directional probabilities, and live market data fields.
    """
    ticker = request.ticker.upper()

    # --- Live market context (graceful degradation on failure) ---------
    market_context = None
    try:
        market_context = await MarketDataAggregator().fetch_context(ticker)
    except Exception as exc:  # noqa: BLE001
        logger.error("[SIMULATE] %s: market context fetch FAILED - %s", ticker, str(exc))

    # --- Core simulation -----------------------------------------------
    sim_result = run_simulation(
        ticker=ticker,
        catalyst=request.catalyst,
        horizon_minutes=request.horizon_minutes,
        market_context=market_context,
    )

    memory_context_rows = get_recent_runs(ticker=ticker, limit=4)
    # Exclude the just-saved current run from response history summary.
    memory_context_rows = memory_context_rows[1:4] if memory_context_rows else []
    memory_context = [
        {
            "catalyst": str(row.get("catalyst", "")),
            "probability_up": float(row.get("probability_up", 0.0)),
            "direction": str(row.get("direction", "neutral")),
            "created_at": str(row.get("created_at", "")),
        }
        for row in memory_context_rows
    ]

    # --- Build response ------------------------------------------------
    total_agents = int(sim_result.get("agent_count", 0))
    bullish_count = int(sim_result.get("up_count", 0))
    bearish_count = int(sim_result.get("down_count", 0))

    if total_agents > 0:
        raw_probability_up = bullish_count / total_agents
        raw_probability_down = bearish_count / total_agents
    else:
        raw_probability_up = 0.0
        raw_probability_down = 0.0

    catalyst_bias = float(
        (sim_result.get("catalyst_analysis") or {}).get("final_bias", 0.0)
    )
    probability_up, probability_down = blend_probabilities(
        raw_probability_up,
        raw_probability_down,
        catalyst_bias,
    )

    # --- Verdict -----------------------------------------------------------
    verdict_data = compute_verdict(
        probability_up=probability_up,
        probability_down=probability_down,
        catalyst_bias=catalyst_bias,
        mean_stance=float(sim_result.get("mean_stance", 0.0)),
        current_price=market_context.current_price if market_context else None,
        ticker=ticker,
        persona_mean_stance=sim_result.get("persona_mean_stance"),
    )
    verdict = VerdictResponse(**verdict_data)

    # Persist the blended-probability verdict onto the DB row written by the runner.
    update_verdict_on_latest_run(
        ticker,
        request.catalyst,
        verdict_action=verdict.action,
        verdict_confidence=verdict.confidence,
        verdict_entry_price=verdict.entry_price,
        verdict_target_price=verdict.target_price,
        verdict_stop_price=verdict.stop_price,
    )

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
        ticker=ticker,
        catalyst=request.catalyst,
        horizon_minutes=request.horizon_minutes,
        aggregate_stance=float(sim_result.get("mean_stance", 0.0)),
        probability_up=probability_up,
        probability_down=probability_down,
        personas=personas,
        catalyst_analysis=sim_result.get("catalyst_analysis"),
        memory_context=memory_context,
        crowd_narrative=sim_result.get("crowd_narrative", []),
        verdict=verdict,
        # Market context fields (None when context fetch failed)
        current_price=market_context.current_price if market_context else None,
        volume_vs_avg=market_context.volume_vs_avg if market_context else None,
    )
