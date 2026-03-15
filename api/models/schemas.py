"""Pydantic v2 request / response schemas for the Crowd Signal API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SimulateRequest(BaseModel):
    """Payload for the POST /api/v1/simulate endpoint.

    Attributes:
        ticker:           The equity ticker to simulate (e.g. ``"NVDA"``).
        catalyst:         Free-text description of the market-moving event
                          (e.g. ``"earnings beat by 20%"``).
        horizon_minutes:  Forward-looking simulation window in minutes.
                          Accepted range: 60–240 (1–4 hours).
    """

    ticker: str = Field(..., min_length=1, max_length=10, examples=["NVDA"])
    catalyst: str = Field(..., min_length=1, examples=["Earnings beat by 20%"])
    horizon_minutes: int = Field(
        default=60,
        ge=60,
        le=240,
        description="Simulation horizon in minutes (60–240).",
    )


class PersonaSentiment(BaseModel):
    """Sentiment breakdown for a single trader persona.

    Attributes:
        persona:    Persona identifier string.
        stance:     Mean stance across all agents of this persona type [-1.0, 1.0].
        confidence: Mean confidence score [0.0, 1.0].
        weight:     Fraction of the total agent population this persona represents.
    """

    persona: str
    stance: float
    confidence: float
    weight: float


class SimulationResult(BaseModel):
    """Response payload from POST /api/v1/simulate.

    Attributes:
        ticker:           The queried ticker.
        catalyst:         The catalyst passed in the request.
        horizon_minutes:  Simulation horizon echoed back.
        aggregate_stance: Population-weighted mean stance [-1.0, 1.0].
        probability_up:   Estimated probability of net upward price movement.
        probability_down: Estimated probability of net downward price movement.
        personas:         Per-persona sentiment breakdown.
    """

    ticker: str
    catalyst: str
    horizon_minutes: int
    aggregate_stance: float
    probability_up: float
    probability_down: float
    personas: list[PersonaSentiment]
