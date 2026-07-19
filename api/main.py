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

from api.routes.accuracy import router as accuracy_router
from api.routes.admin import router as admin_router
from api.routes.daily_report import router as daily_report_router
from api.routes.simulate import router as simulate_router
from api.routes.tickers import router as tickers_router
from api.routes.ws_simulate import router as ws_simulate_router
from engine.backtesting.scheduler import start_scorer_scheduler

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
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://crowd-signal-rose.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(simulate_router, prefix="/api/v1")
app.include_router(tickers_router, prefix="/api/v1")
app.include_router(accuracy_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(daily_report_router, prefix="/api/v1")
app.include_router(ws_simulate_router)

_scorer_scheduler = None


@app.on_event("startup")
async def startup_events() -> None:
    global _scorer_scheduler
    try:
        _scorer_scheduler = start_scorer_scheduler()
    except Exception:
        _scorer_scheduler = None


@app.on_event("shutdown")
async def shutdown_events() -> None:
    global _scorer_scheduler
    try:
        if _scorer_scheduler is not None:
            _scorer_scheduler.shutdown(wait=False)
    except Exception:
        pass
    finally:
        _scorer_scheduler = None


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
