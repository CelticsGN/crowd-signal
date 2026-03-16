"""Ticker-level memory bias adjustment for simulation priming."""

from __future__ import annotations

from engine.memory.db import get_recent_runs


def _clamp(value: float) -> float:
    return max(-1.0, min(1.0, value))


def compute_memory_bias(ticker: str, current_bias: float) -> tuple[float, list[str]]:
    """Adjust current bias using recent ticker memory from persistent storage."""
    recent = get_recent_runs(ticker=ticker, limit=3)
    if not recent:
        return _clamp(current_bias), []

    bullish_count = sum(1 for run in recent if float(run.get("probability_up", 0.0)) > 0.6)
    bearish_count = sum(1 for run in recent if float(run.get("probability_down", 0.0)) > 0.6)

    memory_boost = 0.0
    reason = ""

    if bullish_count >= 2:
        memory_boost = 0.08
        reason = "crowd primed bullish from recent history"
    elif bearish_count >= 2:
        memory_boost = -0.08
        reason = "crowd primed bearish from recent history"

    adjusted_bias = _clamp(current_bias + memory_boost)
    return adjusted_bias, ([reason] if reason else [])
