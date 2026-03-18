from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from api.models.schemas import PersonaSentiment, SimulateRequest, SimulationResult
from engine.data.aggregator import MarketDataAggregator
from engine.memory.db import get_recent_runs
from engine.sim.streaming_runner import run_simulation_streaming

router = APIRouter()
logger = logging.getLogger(__name__)

_PERSONAS = ["retail_bull", "retail_bear", "whale", "algo"]


def _build_simulation_response(result: dict[str, Any], request: SimulateRequest) -> SimulationResult:
    market_context = result.get("market_context") or {}

    total_agents = int(result.get("agent_count", 0))
    bullish_count = int(result.get("up_count", 0))
    bearish_count = int(result.get("down_count", 0))

    if total_agents > 0:
        raw_probability_up = bullish_count / total_agents
        raw_probability_down = bearish_count / total_agents
    else:
        raw_probability_up = 0.0
        raw_probability_down = 0.0

    catalyst_bias = float((result.get("catalyst_analysis") or {}).get("final_bias", 0.0))
    bias_probability_up = max(0.0, min(1.0, 0.5 + (0.37 * catalyst_bias)))
    bias_probability_down = max(0.0, min(1.0, 0.5 - (0.37 * catalyst_bias)))

    blend_weight = 0.9
    probability_up = ((1.0 - blend_weight) * raw_probability_up) + (blend_weight * bias_probability_up)
    probability_down = ((1.0 - blend_weight) * raw_probability_down) + (blend_weight * bias_probability_down)

    memory_context_rows = get_recent_runs(ticker=request.ticker, limit=4)
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

    persona_counts = result.get("persona_counts", {})
    persona_mean_stance = result.get("persona_mean_stance", {})
    persona_mean_confidence = result.get("persona_mean_confidence", {})

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
        ticker=request.ticker,
        catalyst=request.catalyst,
        horizon_minutes=request.horizon_minutes,
        aggregate_stance=float(result.get("mean_stance", 0.0)),
        probability_up=probability_up,
        probability_down=probability_down,
        personas=personas,
        catalyst_analysis=result.get("catalyst_analysis"),
        memory_context=memory_context,
        crowd_narrative=result.get("crowd_narrative", []),
        current_price=market_context.get("current_price"),
        volume_vs_avg=market_context.get("volume_vs_avg"),
        reddit_mentions=market_context.get("reddit_mentions"),
        reddit_sentiment=market_context.get("reddit_sentiment"),
    )


@router.websocket("/ws/simulate")
async def ws_simulate(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        payload = await websocket.receive_json()
    except Exception:
        await websocket.send_json({"type": "error", "message": "Invalid JSON payload."})
        await websocket.close(code=1003)
        return

    try:
        request = SimulateRequest.model_validate(payload)
    except ValidationError as exc:
        await websocket.send_json({"type": "error", "message": "Invalid request payload.", "details": exc.errors()})
        await websocket.close(code=1008)
        return

    market_context = None
    try:
        market_context = await MarketDataAggregator().fetch_context(request.ticker)
    except Exception as exc:  # noqa: BLE001
        logger.error("[WS] %s: market context fetch FAILED - %s", request.ticker, str(exc))
        market_context = None

    active = True
    last_pong_ts = time.monotonic()

    async def heartbeat_sender() -> None:
        while active:
            await asyncio.sleep(10)
            if not active:
                break
            await websocket.send_json({"type": "ping"})

    async def receive_loop() -> None:
        nonlocal last_pong_ts
        while active:
            message = await websocket.receive_json()
            if isinstance(message, dict) and message.get("type") == "pong":
                last_pong_ts = time.monotonic()

    heartbeat_task = asyncio.create_task(heartbeat_sender())
    receive_task = asyncio.create_task(receive_loop())

    try:
        async for event in run_simulation_streaming(
            ticker=request.ticker,
            catalyst=request.catalyst,
            horizon_minutes=request.horizon_minutes,
            market_context=market_context,
        ):
            if event.get("type") == "complete":
                final_result = event.get("result") or {}
                response_model = _build_simulation_response(final_result, request)
                event = {"type": "complete", "result": response_model.model_dump()}
            await websocket.send_json(event)
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Simulation stream failed.",
                "details": str(exc),
            })
        except Exception:
            pass
    finally:
        active = False
        heartbeat_task.cancel()
        receive_task.cancel()
        await asyncio.gather(heartbeat_task, receive_task, return_exceptions=True)
        _ = last_pong_ts
        try:
            await websocket.close()
        except Exception:
            pass
