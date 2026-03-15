"""YFinance connector — fetches OHLCV bars and options chain data."""

from __future__ import annotations

import yfinance as yf

from .base_connector import BaseConnector


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
        results: list[dict] = []

        tkr = yf.Ticker(ticker)

        # --- OHLCV bars ------------------------------------------------
        hist = tkr.history(period=self.period, interval=self.interval)
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

        # --- Options chain (nearest expiry) ----------------------------
        try:
            expiry = tkr.options[0] if tkr.options else None
            if expiry:
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
        except Exception:
            # Options may not be available for all tickers / off-hours
            pass

        return results
