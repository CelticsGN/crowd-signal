"""Tickers route — GET /api/v1/tickers."""

from __future__ import annotations

from fastapi import APIRouter

from api.ticker_catalog import TICKERS

router = APIRouter()


@router.get("/tickers", response_model=dict[str, list[dict[str, str]]])
async def get_tickers() -> dict[str, list[dict[str, str]]]:
    """Return the list of tickers supported by the simulation engine.

    Returns:
        Grouped ticker metadata by market region.
    """
    return TICKERS
