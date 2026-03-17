"""Shared ticker catalog for supported simulation symbols."""

from __future__ import annotations

TICKERS: dict[str, list[dict[str, str]]] = {
    "US": [
        {"symbol": "NVDA", "name": "NVIDIA", "exchange": "NASDAQ", "currency": "USD"},
        {"symbol": "TSLA", "name": "Tesla", "exchange": "NASDAQ", "currency": "USD"},
        {"symbol": "META", "name": "Meta", "exchange": "NASDAQ", "currency": "USD"},
        {"symbol": "AAPL", "name": "Apple", "exchange": "NASDAQ", "currency": "USD"},
        {"symbol": "AMD", "name": "AMD", "exchange": "NASDAQ", "currency": "USD"},
    ],
    "IN": [
        {"symbol": "RELIANCE.NS", "name": "Reliance Industries", "exchange": "NSE", "currency": "INR"},
        {"symbol": "TCS.NS", "name": "Tata Consultancy Services", "exchange": "NSE", "currency": "INR"},
        {"symbol": "INFY.NS", "name": "Infosys", "exchange": "NSE", "currency": "INR"},
        {"symbol": "HDFCBANK.NS", "name": "HDFC Bank", "exchange": "NSE", "currency": "INR"},
        {"symbol": "TATASTEEL.NS", "name": "Tata Steel", "exchange": "NSE", "currency": "INR"},
        {"symbol": "WIPRO.NS", "name": "Wipro", "exchange": "NSE", "currency": "INR"},
        {"symbol": "BAJFINANCE.NS", "name": "Bajaj Finance", "exchange": "NSE", "currency": "INR"},
        {"symbol": "ICICIBANK.NS", "name": "ICICI Bank", "exchange": "NSE", "currency": "INR"},
        {"symbol": "SUNPHARMA.NS", "name": "Sun Pharma", "exchange": "NSE", "currency": "INR"},
        {"symbol": "TATAMOTORS.NS", "name": "Tata Motors", "exchange": "NSE", "currency": "INR"},
    ],
}

ALLOWED_TICKERS: set[str] = {
    row["symbol"].upper()
    for group in TICKERS.values()
    for row in group
}
