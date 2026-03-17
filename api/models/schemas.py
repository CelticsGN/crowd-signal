"""Pydantic v2 request / response schemas for the Crowd Signal API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from api.ticker_catalog import ALLOWED_TICKERS


class SimulateRequest(BaseModel):
    """Payload for the POST /api/v1/simulate endpoint.

    Attributes:
        ticker:           The equity ticker to simulate (e.g. ``"NVDA"``).
        catalyst:         Free-text description of the market-moving event
                          (e.g. ``"earnings beat by 20%"``).
        horizon_minutes:  Forward-looking simulation window in minutes.
                          Accepted range: 60–240 (1–4 hours).
    """

    ticker: str = Field(..., min_length=1, max_length=20, examples=["NVDA", "RELIANCE.NS"])
    catalyst: str = Field(..., min_length=1, examples=["Earnings beat by 20%"])
    horizon_minutes: int = Field(
        default=60,
        ge=60,
        le=240,
        description="Simulation horizon in minutes (60–240).",
    )

    @field_validator("ticker")
    @classmethod
    def validate_supported_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in ALLOWED_TICKERS:
            raise ValueError("Ticker is not in supported US/IN catalog")
        return normalized


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


class CatalystExtraction(BaseModel):
    """Structured catalyst entities extracted in analysis step 1."""

    primary_entity: str
    event_type: str
    magnitude: str
    direction: str
    related_entities: list[str]


class CatalystGraphNode(BaseModel):
    """Node in the catalyst relationship graph."""

    id: str
    kind: str


class CatalystGraphEdge(BaseModel):
    """Directed weighted relation in the catalyst relationship graph."""

    source: str
    target: str
    relation: str
    weight: float


class CatalystReasoningEntry(BaseModel):
    """Single rule explanation for catalyst bias construction."""

    rule: str
    effect: str
    weight: float
    detail: str


class CatalystAnalysis(BaseModel):
    """Enriched catalyst bias payload with transparent reasoning."""

    extraction: CatalystExtraction
    graph_nodes: list[CatalystGraphNode]
    graph_edges: list[CatalystGraphEdge]
    base_bias: float
    graph_adjustment: float
    market_adjustment: float
    final_bias: float
    market_scope: str
    reasoning: list[CatalystReasoningEntry]


class MemoryEntry(BaseModel):
    """Summary of a recent simulation memory row for a ticker."""

    catalyst: str
    probability_up: float
    direction: str
    created_at: str


class NarrativeEntry(BaseModel):
    """Single vocal-agent narrative message from the simulation."""

    agent_id: str
    persona: str
    message: str
    stance: float


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
        current_price:    Live price from yfinance (None if unavailable).
        volume_vs_avg:    Today's volume / 30-day avg (None if unavailable).
        reddit_mentions:  Reddit posts mentioning ticker in last 2 h (None if unavailable).
        reddit_sentiment: Bag-of-words Reddit sentiment in [-1, 1] (None if unavailable).
    """

    ticker: str
    catalyst: str
    horizon_minutes: int
    aggregate_stance: float
    probability_up: float
    probability_down: float
    personas: list[PersonaSentiment]
    catalyst_analysis: Optional[CatalystAnalysis] = None
    memory_context: Optional[list[MemoryEntry]] = None
    crowd_narrative: Optional[list[NarrativeEntry]] = None

    # Live market context fields — all Optional for graceful degradation
    current_price: Optional[float] = None
    volume_vs_avg: Optional[float] = None
    reddit_mentions: Optional[int] = None
    reddit_sentiment: Optional[float] = None


class TickerAccuracyEntry(BaseModel):
    """Directional prediction accuracy summary."""

    total: int
    correct: int
    accuracy_pct: float


class AccuracyStats(BaseModel):
    """Global and per-ticker directional accuracy payload."""

    global_accuracy: TickerAccuracyEntry
    by_ticker: dict[str, TickerAccuracyEntry]
    last_updated: str
