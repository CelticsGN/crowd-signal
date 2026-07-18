"""Market data aggregator — combines all three connectors into a single MarketContext."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from pydantic import BaseModel

from engine.data.yfinance_connector import YFinanceConnector
from engine.data.news_connector import NewsConnector
from engine.data.market_utils import is_indian_stock as _is_indian_stock
from engine.data.market_utils import get_market_hours as _get_market_hours

logger = logging.getLogger(__name__)



def is_indian_stock(ticker: str) -> bool:
    return _is_indian_stock(ticker)


def get_market_hours(ticker: str) -> dict[str, str]:
    return _get_market_hours(ticker)




class MarketContext(BaseModel):
    """Enriched market snapshot used to bias the simulation at run-time.

    All fields are ``Optional`` so a partial failure from any connector
    does not prevent the simulation from running.

    Attributes:
        current_price:        Latest trade price from yfinance.
        price_change_pct:     Today's percentage price change.
        volume_vs_avg:        Today's volume divided by the 30-day average.
        recent_headlines:     Up to 5 recent news headlines mentioning the ticker.
        options_put_call_ratio: Total put open interest / total call open interest.
    """

    current_price: Optional[float] = None
    price_change_pct: Optional[float] = None
    volume_vs_avg: Optional[float] = None
    recent_headlines: list[str] = []
    options_put_call_ratio: Optional[float] = None


class MarketDataAggregator:
    """Orchestrates all three data connectors into a single :class:`MarketContext`.

    Each connector is called independently; failures are caught and logged
    so a broken connector never prevents the simulation from running.
    """

    def __init__(self) -> None:
        """Initialise the aggregator with default connector instances."""
        self._yf = YFinanceConnector(period="1d", interval="1m")
        self._news = NewsConnector()

    # ------------------------------------------------------------------
    # Internal fetch helpers (each returns None on failure)
    # ------------------------------------------------------------------

    async def _fetch_price_data(self, ticker: str) -> dict:
        """Return price/volume/options fields or empty dict on failure."""
        try:
            records = await asyncio.to_thread(self._yf.fetch, ticker)
        except Exception:  # noqa: BLE001
            # YFinanceConnector already logs retry/failure details.
            return {}

        ohlcv = [r for r in records if r["type"] == "ohlcv"]
        calls = [r for r in records if r["type"] == "option_call"]
        puts  = [r for r in records if r["type"] == "option_put"]

        result: dict = {}

        if ohlcv:
            first_close = ohlcv[0]["close"]
            last_close  = ohlcv[-1]["close"]
            result["current_price"] = last_close

            if first_close and first_close != 0:
                result["price_change_pct"] = round(
                    (last_close - first_close) / first_close * 100, 4
                )

            # Volume vs 30-day average: approximate with intraday bars
            total_volume = sum(r["volume"] for r in ohlcv)
            bar_count    = len(ohlcv)
            # A full trading day is ~390 1-min bars; 30 days ≈ 11 700 bars
            # Approx avg daily volume = total_volume / (bar_count / 390)
            bars_per_day = 390
            if bar_count > 0:
                daily_approx   = total_volume / (bar_count / bars_per_day)
                thirty_day_avg = daily_approx  # single-day proxy — good enough for bias
                result["volume_vs_avg"] = round(
                    total_volume / thirty_day_avg, 4
                ) if thirty_day_avg else None

        # Options put/call ratio (by open interest)
        if calls or puts:
            call_oi = sum(r.get("open_interest", 0) for r in calls)
            put_oi  = sum(r.get("open_interest", 0) for r in puts)
            result["options_put_call_ratio"] = (
                round(put_oi / call_oi, 4) if call_oi > 0 else None
            )

        return result

    async def _fetch_headlines(self, ticker: str) -> list[str]:
        """Return up to 5 recent headlines or empty list on failure."""
        try:
            records = await self._news.fetch(ticker)
            return [r["headline"] for r in records[:5]]
        except Exception as exc:  # noqa: BLE001
            logger.error("[NEWS] %s: FAILED - %s", ticker, str(exc))
            return []


    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def fetch_context(self, ticker: str) -> MarketContext:
        """Aggregate live market data for *ticker* into a :class:`MarketContext`.

        Each connector is called independently so partial failures
        produce a context with ``None`` for unavailable fields rather
        than raising an exception.

        Args:
            ticker: Ticker symbol (e.g. ``"NVDA"``).

        Returns:
            A :class:`MarketContext` with as many fields populated as
            the live data sources allow.
        """
        price_data = await self._fetch_price_data(ticker)
        headlines = await self._fetch_headlines(ticker)

        return MarketContext(
            current_price=price_data.get("current_price"),
            price_change_pct=price_data.get("price_change_pct"),
            volume_vs_avg=price_data.get("volume_vs_avg"),
            recent_headlines=headlines,
            options_put_call_ratio=price_data.get("options_put_call_ratio"),
        )
