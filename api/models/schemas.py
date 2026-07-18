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


class VerdictResponse(BaseModel):
    """Structured BUY / SELL / HOLD trading verdict derived from the simulation.

    Attributes:
        action:            One of ``BUY``, ``SELL``, ``HOLD``.
        confidence:        Conviction score 0-100 (scales with distance from 0.50).
        entry_price:       Current market price at time of simulation (None if unavailable).
        target_price:      Price target in the direction of the call (None for HOLD / price unavailable).
        stop_price:        Stop-loss level (None for HOLD / price unavailable).
        range_low:         HOLD neutral band lower bound (None for BUY/SELL).
        range_high:        HOLD neutral band upper bound (None for BUY/SELL).
        reasoning_summary: 1-2 sentence plain-English explanation of why.
        used_fallback:     True when ATR data was unavailable and flat-% logic was used.
    """

    action: str
    confidence: int
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_price: Optional[float] = None
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    reasoning_summary: str
    used_fallback: bool = True


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

    # Structured verdict — the headline BUY/SELL/HOLD call
    verdict: Optional[VerdictResponse] = None

    # Live market context fields — all Optional for graceful degradation
    current_price: Optional[float] = None
    volume_vs_avg: Optional[float] = None


class TickerAccuracyEntry(BaseModel):
    """Directional prediction accuracy summary."""

    directional_total: int
    directional_correct: int
    directional_accuracy_pct: float
    hold_total: int
    hold_correct: int
    hold_accuracy_pct: float


class AccuracyStats(BaseModel):
    """Global and per-ticker directional accuracy payload."""

    global_accuracy: TickerAccuracyEntry
    by_ticker: dict[str, TickerAccuracyEntry]
    last_updated: str


class RecentRunEntry(BaseModel):
    """A recently scored simulation run."""

    ticker: str
    action: str
    confidence: Optional[int] = None
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_price: Optional[float] = None
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    prediction_correct: Optional[bool] = None
    actual_price_24h: Optional[float] = None
    created_at: str


class RecentRunsResponse(BaseModel):
    """Response payload for recent scored runs."""

    runs: list[RecentRunEntry]


class DailyReportEntry(BaseModel):
    """Single ticker entry in the generated morning report."""

    ticker: str
    catalyst: str
    headline: str
    priority: str
    aggregate_stance: float
    probability_up: float
    probability_down: float
    crowd_verdict: str
    verdict_strength: str
    currency: str


class DailyReportResponse(BaseModel):
    """Daily report API payload for landing and manual checks."""

    report_date: str
    generated_at: str
    us_entries: list[DailyReportEntry]
    in_entries: list[DailyReportEntry]
    accuracy_this_week: float
    correct_this_week: int
    total_this_week: int
    status: str
    message: Optional[str] = None
