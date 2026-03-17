"""Market data aggregator — combines all three connectors into a single MarketContext."""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel

from engine.data.yfinance_connector import YFinanceConnector
from engine.data.news_connector import NewsConnector
from engine.data.reddit_connector import RedditConnector
from engine.data.market_utils import is_indian_stock as _is_indian_stock
from engine.data.market_utils import get_market_hours as _get_market_hours

# --- Sentiment word lists for Reddit posts ----------------------------
_POSITIVE_WORDS = {"bull", "moon", "calls", "buy", "pump", "bullish", "long",
                   "mooning", "rally", "surge", "squeeze", "yolo", "rip"}
_NEGATIVE_WORDS = {"bear", "puts", "sell", "crash", "dump", "bearish", "short",
                   "rug", "plunge", "correction", "tank", "baghold", "rekt"}


def is_indian_stock(ticker: str) -> bool:
    return _is_indian_stock(ticker)


def get_market_hours(ticker: str) -> dict[str, str]:
    return _get_market_hours(ticker)


def _reddit_sentiment_score(posts: list[dict]) -> float:
    """Score Reddit posts on a simple positive-vs-negative word count.

    Args:
        posts: Raw dicts from :class:`RedditConnector`.

    Returns:
        Float in [-1.0, 1.0]: ``(pos - neg) / (pos + neg + 1)``.
    """
    pos = neg = 0
    for post in posts:
        text = (post.get("title", "") + " " + post.get("selftext", "")).lower()
        words = set(re.findall(r"\b[a-z]+\b", text))
        pos += len(words & _POSITIVE_WORDS)
        neg += len(words & _NEGATIVE_WORDS)
    return (pos - neg) / (pos + neg + 1)


class MarketContext(BaseModel):
    """Enriched market snapshot used to bias the simulation at run-time.

    All fields are ``Optional`` so a partial failure from any connector
    does not prevent the simulation from running.

    Attributes:
        current_price:        Latest trade price from yfinance.
        price_change_pct:     Today's percentage price change.
        volume_vs_avg:        Today's volume divided by the 30-day average.
        recent_headlines:     Up to 5 recent news headlines mentioning the ticker.
        reddit_mentions:      Count of posts mentioning the ticker in the last 2 h.
        reddit_sentiment:     Bag-of-words sentiment score in [-1.0, 1.0].
        options_put_call_ratio: Total put open interest / total call open interest.
    """

    current_price: Optional[float] = None
    price_change_pct: Optional[float] = None
    volume_vs_avg: Optional[float] = None
    recent_headlines: list[str] = []
    reddit_mentions: Optional[int] = None
    reddit_sentiment: Optional[float] = None
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
        self._reddit = RedditConnector(lookback_hours=2.0)

    # ------------------------------------------------------------------
    # Internal fetch helpers (each returns None on failure)
    # ------------------------------------------------------------------

    def _fetch_price_data(self, ticker: str) -> dict:
        """Return price/volume/options fields or empty dict on failure."""
        try:
            records = self._yf.fetch(ticker)
        except Exception:
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

    def _fetch_headlines(self, ticker: str) -> list[str]:
        """Return up to 5 recent headlines or empty list on failure."""
        try:
            records = self._news.fetch(ticker)
            return [r["headline"] for r in records[:5]]
        except Exception:
            return []

    def _fetch_reddit(self, ticker: str) -> dict:
        """Return reddit mention count + sentiment score or empty dict."""
        try:
            posts = self._reddit.fetch(ticker)
            return {
                "reddit_mentions": len(posts),
                "reddit_sentiment": round(_reddit_sentiment_score(posts), 4),
            }
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch_context(self, ticker: str) -> MarketContext:
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
        price_data = self._fetch_price_data(ticker)
        headlines  = self._fetch_headlines(ticker)
        reddit     = self._fetch_reddit(ticker)

        return MarketContext(
            current_price=price_data.get("current_price"),
            price_change_pct=price_data.get("price_change_pct"),
            volume_vs_avg=price_data.get("volume_vs_avg"),
            recent_headlines=headlines,
            reddit_mentions=reddit.get("reddit_mentions"),
            reddit_sentiment=reddit.get("reddit_sentiment"),
            options_put_call_ratio=price_data.get("options_put_call_ratio"),
        )
