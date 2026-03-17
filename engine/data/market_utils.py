"""Market helpers for ticker-specific exchange routing."""

from __future__ import annotations


def is_indian_stock(ticker: str) -> bool:
    symbol = (ticker or "").upper()
    return symbol.endswith(".NS") or symbol.endswith(".BO")


def get_market_hours(ticker: str) -> dict[str, str]:
    if is_indian_stock(ticker):
        return {
            "open": "09:15",
            "close": "15:30",
            "timezone": "Asia/Kolkata",
            "exchange": "NSE",
        }

    return {
        "open": "09:30",
        "close": "16:00",
        "timezone": "America/New_York",
        "exchange": "NASDAQ/NYSE",
    }
