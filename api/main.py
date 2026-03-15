"""Crowd Signal — FastAPI application entry point.

Exposes three endpoints:
* ``GET  /health``              — liveness check
* ``POST /api/v1/simulate``     — run crowd simulation for a catalyst
* ``GET  /api/v1/tickers``      — list supported tickers

CORS is pre-configured for a Next.js dev server on ``http://localhost:3000``.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.simulate import router as simulate_router
from api.routes.tickers import router as tickers_router

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Crowd Signal API",
    description=(
        "AI-powered stock market crowd simulation. "
        "Accepts a ticker + catalyst and returns a probabilistic sentiment map "
        "derived from simulated retail, whale, and algo trader personas."
    ),
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(simulate_router, prefix="/api/v1")
app.include_router(tickers_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe — returns ``{"status": "ok"}`` when the server is running.

    Returns:
        A dict with a single ``status`` key set to ``"ok"``.
    """
    return {"status": "ok"}
