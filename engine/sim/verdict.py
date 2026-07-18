"""Verdict derivation from completed simulation state.

Converts the probabilistic simulation output into a structured trading verdict
(BUY / SELL / HOLD) with confidence score, ATR-calibrated price targets, and a
one-line reasoning summary.

All tuneable thresholds are defined as module-level constants so they can be
adjusted in one place without touching business logic.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, TypedDict

from engine.data.yfinance_connector import compute_atr_14

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Verdict thresholds — tune these, not the logic below.
# ---------------------------------------------------------------------------

# probability_up >= BUY_THRESHOLD  → BUY
# probability_down >= SELL_THRESHOLD → SELL
# everything else                   → HOLD
BUY_THRESHOLD: float = 0.54
SELL_THRESHOLD: float = 0.54

# Confidence scales with the actual distance of the triggering probability
# from the neutral 0.50 midpoint, so a marginal 0.54 call looks visibly
# weaker than a decisive 0.75 call.
#
# Formula:
#   dominant_prob = max(probability_up, probability_down)
#   distance      = dominant_prob - 0.50          (0.0 at neutral, 0.50 at max)
#   confidence    = CONFIDENCE_FLOOR + (100 - CONFIDENCE_FLOOR) * min(distance / CONFIDENCE_MAX_DISTANCE, 1.0)
#
# At threshold 0.54 → distance=0.04 → confidence ≈ 31
# At 0.65           → distance=0.15 → confidence ≈ 56
# At 0.80           → distance=0.30 → confidence ≈ 87
CONFIDENCE_FLOOR: int = 25
CONFIDENCE_MAX_DISTANCE: float = 0.40

# ATR-based price-target multipliers.
# BUY:  target = entry + (ATR_TARGET_MULT * ATR),  stop = entry − (ATR_STOP_MULT * ATR)
# SELL: target = entry − (ATR_TARGET_MULT * ATR),  stop = entry + (ATR_STOP_MULT * ATR)
# HOLD: range_high = entry + (ATR_HOLD_RANGE_MULT * ATR)
#       range_low  = entry − (ATR_HOLD_RANGE_MULT * ATR)
# Preserves ~2:1 reward-to-risk.
ATR_TARGET_MULT: float = 3.0
ATR_STOP_MULT: float = 1.5
ATR_HOLD_RANGE_MULT: float = 1.0

# Flat-percentage fallback when ATR can't be computed.
FALLBACK_TARGET_PCT: float = 0.04   # ±4 %
FALLBACK_STOP_PCT: float = 0.02     # ±2 %
FALLBACK_HOLD_RANGE_PCT: float = 0.015  # ±1.5 %


# ---------------------------------------------------------------------------
# Verdict type
# ---------------------------------------------------------------------------

class Verdict(TypedDict, total=False):
    action: str                     # "BUY" | "SELL" | "HOLD"
    confidence: int                 # 0–100
    entry_price: float | None       # None when price unavailable
    target_price: float | None      # None for HOLD
    stop_price: float | None        # None for HOLD
    range_low: float | None         # HOLD neutral band lower bound
    range_high: float | None        # HOLD neutral band upper bound
    reasoning_summary: str
    used_fallback: bool             # True when ATR was unavailable


# ---------------------------------------------------------------------------
# Core derivation
# ---------------------------------------------------------------------------

def blend_probabilities(
    raw_probability_up: float,
    raw_probability_down: float,
    catalyst_bias: float,
) -> tuple[float, float]:
    """Blend raw simulation agent probabilities with the catalyst bias prior."""
    bias_probability_up = max(0.0, min(1.0, 0.5 + (0.37 * catalyst_bias)))
    bias_probability_down = max(0.0, min(1.0, 0.5 - (0.37 * catalyst_bias)))
    blend_weight = 0.9
    prob_up = ((1.0 - blend_weight) * raw_probability_up) + (blend_weight * bias_probability_up)
    prob_down = ((1.0 - blend_weight) * raw_probability_down) + (blend_weight * bias_probability_down)
    return prob_up, prob_down


def compute_verdict(
    *,
    probability_up: float,
    probability_down: float,
    catalyst_bias: float,
    mean_stance: float,
    current_price: float | None,
    ticker: str = "",
    persona_mean_stance: dict[str, float] | None = None,
) -> Verdict:
    """Derive a structured verdict from completed simulation numbers.

    Parameters
    ----------
    probability_up / probability_down
        Blended probabilities already computed by the simulate route
        (agent-population ratio + bias prior).
    catalyst_bias
        The ``final_bias`` value from catalyst analysis (−1 to +1).
    mean_stance
        Population-wide mean agent stance after all ticks.
    current_price
        Live market price from yfinance.  ``None`` when the price fetch
        failed — in that case entry/target/stop will all be ``None``.
    ticker
        Ticker symbol, used to fetch ATR.  If empty, ATR is skipped and
        the flat-percentage fallback is used.
    persona_mean_stance
        Optional per-persona stance dict for richer reasoning text.

    Returns
    -------
    Verdict
        Structured dict with action, confidence, prices, and reasoning.
    """

    # --- Action decision ---------------------------------------------------
    if probability_up >= BUY_THRESHOLD:
        action: Literal["BUY", "SELL", "HOLD"] = "BUY"
    elif probability_down >= SELL_THRESHOLD:
        action = "SELL"
    else:
        action = "HOLD"

    # --- Confidence (0-100) ------------------------------------------------
    # Scales with actual distance from the 0.50 neutral midpoint so that a
    # marginal call at the threshold edge (0.54) shows visibly lower
    # confidence than a strong call at 0.75+.
    dominant_prob = max(probability_up, probability_down)
    distance = max(0.0, dominant_prob - 0.50)
    raw_confidence = CONFIDENCE_FLOOR + (100 - CONFIDENCE_FLOOR) * min(
        distance / CONFIDENCE_MAX_DISTANCE, 1.0
    )
    confidence = int(round(raw_confidence))

    # --- ATR fetch ---------------------------------------------------------
    atr: float | None = None
    used_fallback = True
    if ticker and current_price is not None and current_price > 0:
        atr = compute_atr_14(ticker)
        if atr is not None and atr > 0:
            used_fallback = False

    # --- Price targets -----------------------------------------------------
    entry_price: float | None = None
    target_price: float | None = None
    stop_price: float | None = None
    range_low: float | None = None
    range_high: float | None = None

    if current_price is not None and current_price > 0:
        entry_price = round(current_price, 2)

        if action == "BUY":
            if atr and not used_fallback:
                target_price = round(entry_price + (ATR_TARGET_MULT * atr), 2)
                stop_price = round(entry_price - (ATR_STOP_MULT * atr), 2)
            else:
                target_price = round(entry_price * (1 + FALLBACK_TARGET_PCT), 2)
                stop_price = round(entry_price * (1 - FALLBACK_STOP_PCT), 2)
        elif action == "SELL":
            if atr and not used_fallback:
                target_price = round(entry_price - (ATR_TARGET_MULT * atr), 2)
                stop_price = round(entry_price + (ATR_STOP_MULT * atr), 2)
            else:
                target_price = round(entry_price * (1 - FALLBACK_TARGET_PCT), 2)
                stop_price = round(entry_price * (1 + FALLBACK_STOP_PCT), 2)
        else:
            # HOLD — show a neutral "watching this range" band.
            if atr and not used_fallback:
                range_low = round(entry_price - (ATR_HOLD_RANGE_MULT * atr), 2)
                range_high = round(entry_price + (ATR_HOLD_RANGE_MULT * atr), 2)
            else:
                range_low = round(entry_price * (1 - FALLBACK_HOLD_RANGE_PCT), 2)
                range_high = round(entry_price * (1 + FALLBACK_HOLD_RANGE_PCT), 2)

    # --- Reasoning summary -------------------------------------------------
    reasoning_summary = _build_reasoning(
        action=action,
        confidence=confidence,
        probability_up=probability_up,
        probability_down=probability_down,
        mean_stance=mean_stance,
        persona_mean_stance=persona_mean_stance,
    )

    return {
        "action": action,
        "confidence": confidence,
        "entry_price": entry_price,
        "target_price": target_price,
        "stop_price": stop_price,
        "range_low": range_low,
        "range_high": range_high,
        "reasoning_summary": reasoning_summary,
        "used_fallback": used_fallback,
    }


def _build_reasoning(
    *,
    action: str,
    confidence: int,
    probability_up: float,
    probability_down: float,
    mean_stance: float,
    persona_mean_stance: dict[str, float] | None,
) -> str:
    """Produce a 1-2 sentence plain-English explanation of the verdict."""

    # Identify the dominant persona voice (if available)
    leader = ""
    if persona_mean_stance:
        sorted_personas = sorted(persona_mean_stance.items(), key=lambda kv: abs(kv[1]), reverse=True)
        if sorted_personas:
            top_persona, top_stance = sorted_personas[0]
            label = top_persona.replace("_", " ").title()
            direction = "bullish" if top_stance > 0 else "bearish" if top_stance < 0 else "neutral"
            leader = f"{label} leading the move ({direction}). "

    if action == "BUY":
        return (
            f"Crowd leans bullish with {probability_up:.0%} upside probability "
            f"and {confidence}% conviction. {leader}"
            f"Mean stance is {mean_stance:+.2f}."
        )
    elif action == "SELL":
        return (
            f"Crowd tilts bearish with {probability_down:.0%} downside probability "
            f"and {confidence}% conviction. {leader}"
            f"Mean stance is {mean_stance:+.2f}."
        )
    else:
        return (
            f"Crowd is split — no clear edge. "
            f"Upside {probability_up:.0%} vs downside {probability_down:.0%}. {leader}"
            f"Sitting this one out until the signal clears."
        )
