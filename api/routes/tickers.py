"""Tickers route — GET /api/v1/tickers."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

_SUPPORTED_TICKERS: list[str] = ["NVDA", "TSLA", "META", "AAPL", "AMD"]


@router.get("/tickers", response_model=list[str])
async def get_tickers() -> list[str]:
    """Return the list of tickers supported by the simulation engine.

    Returns:
        A list of uppercase ticker symbols that have been pre-validated
        for use with all three data connectors.
    """
    return _SUPPORTED_TICKERS
