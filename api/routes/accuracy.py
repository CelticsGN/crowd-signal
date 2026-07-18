"""Accuracy routes — GET /api/v1/accuracy and /api/v1/accuracy/{ticker}."""

from __future__ import annotations

from fastapi import APIRouter

from api.models.schemas import AccuracyStats, TickerAccuracyEntry, RecentRunsResponse
from engine.backtesting.scorer import get_accuracy_stats, get_ticker_accuracy, get_recent_scored_runs

router = APIRouter()

@router.get("/accuracy/recent", response_model=RecentRunsResponse)
async def accuracy_recent() -> RecentRunsResponse:
    runs = get_recent_scored_runs(limit=20)
    return RecentRunsResponse(runs=runs)


@router.get("/accuracy", response_model=AccuracyStats)
async def accuracy() -> AccuracyStats:
    payload = get_accuracy_stats()
    return AccuracyStats(
        global_accuracy=payload.get("global_accuracy", {
            "directional_total": 0, "directional_correct": 0, "directional_accuracy_pct": 0.0,
            "hold_total": 0, "hold_correct": 0, "hold_accuracy_pct": 0.0
        }),
        by_ticker=payload.get("by_ticker", {}),
        last_updated=str(payload.get("last_updated", "")),
    )


@router.get("/accuracy/{ticker}", response_model=TickerAccuracyEntry)
async def accuracy_ticker(ticker: str) -> TickerAccuracyEntry:
    payload = get_ticker_accuracy(ticker.upper())
    return TickerAccuracyEntry(
        directional_total=int(payload.get("directional_total", 0)),
        directional_correct=int(payload.get("directional_correct", 0)),
        directional_accuracy_pct=float(payload.get("directional_accuracy_pct", 0.0)),
        hold_total=int(payload.get("hold_total", 0)),
        hold_correct=int(payload.get("hold_correct", 0)),
        hold_accuracy_pct=float(payload.get("hold_accuracy_pct", 0.0)),
    )
