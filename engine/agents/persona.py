"""Trader persona definitions and agent state schema for Crowd Signal."""

from __future__ import annotations

from enum import Enum
from typing import TypedDict


class PersonaType(str, Enum):
    """Enumeration of the simulated trader archetypes.

    Each persona represents a distinct class of market participant with
    different reaction speeds, risk appetites, and information-processing
    tendencies.

    Attributes:
        retail_bull: Optimistic retail trader who buys dips and chases momentum.
        retail_bear: Pessimistic retail trader who shorts or goes to cash quickly.
        whale:       Large institutional or high-net-worth actor whose sizing
                     can itself move the market.
        algo:        Algorithmic / systematic strategy that reacts purely to
                     quantitative signals with minimal latency.
    """

    retail_bull = "retail_bull"
    retail_bear = "retail_bear"
    whale = "whale"
    algo = "algo"


class AgentState(TypedDict):
    """Snapshot of a single simulated agent's current internal state.

    This TypedDict is intentionally minimal — the simulation engine is
    responsible for evolving these values over each time step.

    Attributes:
        stance:       Directional conviction in [-1.0, 1.0].
                      -1.0 = maximally bearish, 0.0 = neutral, 1.0 = maximally bullish.
        persona:      The trader archetype driving this agent's behaviour.
        react_speed:  How quickly the agent responds to new catalyst information,
                      expressed as a fraction of the simulation time-step [0.0, 1.0].
        confidence:   Agent's self-assessed confidence in its current stance [0.0, 1.0].
                      Low confidence widens the probabilistic output band.
    """

    stance: float
    persona: PersonaType
    react_speed: float
    confidence: float
