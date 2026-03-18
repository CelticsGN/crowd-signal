"""YFinance connector — fetches OHLCV bars and options chain data."""

from __future__ import annotations

import logging
import time

import yfinance as yf

from .base_connector import BaseConnector

logger = logging.getLogger(__name__)


def _is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "429" in text or "too many requests" in text or "rate limit" in text


class YFinanceConnector(BaseConnector):
    """Fetches price history (OHLCV) and the options chain for a ticker.

    Uses the ``yfinance`` library which pulls data from Yahoo Finance
    without requiring an API key. By default it fetches the last two
    hours of 1-minute bars plus the nearest-expiry options chain.
    """

    def __init__(self, period: str = "1d", interval: str = "1m") -> None:
        """Initialise the connector.

        Args:
            period:   yfinance period string, e.g. ``"1d"``, ``"5d"``.
            interval: Bar interval, e.g. ``"1m"``, ``"5m"``, ``"1h"``.
        """
        self.period = period
        self.interval = interval

    # ------------------------------------------------------------------
    # BaseConnector implementation
    # ------------------------------------------------------------------

    def fetch(self, ticker: str) -> list[dict]:
        """Fetch OHLCV bars and options chain for *ticker*.

        Args:
            ticker: Ticker symbol (e.g. ``"NVDA"``).

        Returns:
            A list of dicts. Each OHLCV bar is represented as one dict
            with keys ``type``, ``open``, ``high``, ``low``, ``close``,
            ``volume``, and ``timestamp``. Options records share the same
            ``type`` key (``"option_call"`` / ``"option_put"``) together
            with strike, expiry, implied-volatility and open-interest.
        """
        for attempt in range(2):
            try:
                logger.info("[YFINANCE] Fetching data for %s", ticker)
                results: list[dict] = []

                tkr = yf.Ticker(ticker)

                # --- OHLCV bars ------------------------------------------------
                hist = tkr.history(period=self.period, interval=self.interval)
                if hist.empty:
                    raise ValueError(f"No OHLCV data returned for {ticker}")

                for ts, row in hist.iterrows():
                    results.append(
                        {
                            "type": "ohlcv",
                            "ticker": ticker,
                            "timestamp": ts.isoformat(),
                            "open": float(row["Open"]),
                            "high": float(row["High"]),
                            "low": float(row["Low"]),
                            "close": float(row["Close"]),
                            "volume": int(row["Volume"]),
                        }
                    )

                last_close = float(hist.iloc[-1]["Close"])
                last_volume = int(hist.iloc[-1]["Volume"])
                logger.info("[YFINANCE] %s: price=%s, volume=%s", ticker, last_close, last_volume)

                # --- Options chain (nearest expiry) ----------------------------
                expiry = tkr.options[0] if tkr.options else None
                if expiry is None:
                    raise ValueError(f"No options expiry data returned for {ticker}")

                chain = tkr.option_chain(expiry)
                for opt_type, df in (("option_call", chain.calls), ("option_put", chain.puts)):
                    for _, row in df.iterrows():
                        results.append(
                            {
                                "type": opt_type,
                                "ticker": ticker,
                                "expiry": expiry,
                                "strike": float(row.get("strike", 0)),
                                "implied_volatility": float(row.get("impliedVolatility", 0)),
                                "open_interest": int(row.get("openInterest", 0)),
                                "volume": int(row.get("volume", 0) or 0),
                            }
                        )

                return results
            except Exception as exc:  # noqa: BLE001
                if attempt == 0 and _is_rate_limit_error(exc):
                    logger.warning("[YFINANCE] %s: rate limited, retrying in 5s", ticker)
                    time.sleep(5)
                    continue
                logger.error("[YFINANCE] %s: FAILED - %s", ticker, str(exc))
                raise

        raise RuntimeError(f"Unexpected yfinance retry flow for {ticker}")
