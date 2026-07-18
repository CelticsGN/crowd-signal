"""News connector with explicit diagnostics and company-aware matching."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import logging
import os
import re
import time
from threading import Lock
from typing import Awaitable, Callable, Optional

import feedparser
import httpx
from dotenv import load_dotenv

from api.ticker_catalog import TICKERS

from .base_connector import BaseConnector
from .market_utils import is_indian_stock

logger = logging.getLogger(__name__)

load_dotenv()

_news_cache: dict[str, tuple[list, float]] = {}
_news_cache_lock = Lock()
NEWS_CACHE_TTL = 180

ProviderFetcher = Callable[[str], Awaitable[list["NewsEvent"]]]

_HTTP_TIMEOUT = 8.0
_FEED_TIMEOUT_SECONDS = 8
_PER_FEED_DELAY_SECONDS = 0.5
_DEFAULT_LIMIT = 5
_ALPHA_VANTAGE_TIME_FORMAT = "%Y%m%dT%H%M%S"

US_RSS_FEEDS: list[str] = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
]

INDIAN_RSS_FEEDS: list[str] = [
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.moneycontrol.com/rss/MCtopnews.xml",
    "https://www.business-standard.com/rss/markets-106.rss",
]

_COMPANY_NAME_OVERRIDES = {
    "META": "Meta Platforms Facebook",
    "AMD": "Advanced Micro Devices AMD",
    "SUNPHARMA.NS": "Sun Pharma Sun Pharmaceutical",
}

_COMPANY_NAME_LOOKUP = {
    row["symbol"].upper(): row["name"]
    for market_rows in TICKERS.values()
    for row in market_rows
}

_COMMON_NAME_WORDS = {
    "inc",
    "limited",
    "ltd",
    "plc",
    "corporation",
    "corp",
    "group",
    "holdings",
    "company",
    "co",
    "services",
    "industries",
    "bank",
}


@dataclass
class NewsEvent:
    """A normalized news item returned by any upstream provider."""

    headline: str
    summary: str
    published: datetime
    url: str
    source: str
    ticker_mentions: list[str] = field(default_factory=list)


def _clean_ticker(ticker: str) -> str:
    return (ticker or "").upper().replace(".NS", "").replace(".BO", "")


def _normalize_published(value: object) -> datetime:
    """Convert provider-specific timestamps into UTC-aware datetimes."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return datetime.now(tz=timezone.utc)

        if raw.isdigit():
            return datetime.fromtimestamp(int(raw), tz=timezone.utc)

        try:
            return datetime.strptime(raw, _ALPHA_VANTAGE_TIME_FORMAT).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

        iso_candidate = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(iso_candidate)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(raw)
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except (TypeError, ValueError):
                logger.warning("[NEWS] unable to parse published timestamp=%s", raw)

    return datetime.now(tz=timezone.utc)


def get_company_name(ticker: str) -> str:
    symbol = (ticker or "").upper()
    if symbol in _COMPANY_NAME_OVERRIDES:
        return _COMPANY_NAME_OVERRIDES[symbol]

    if symbol in _COMPANY_NAME_LOOKUP:
        return _COMPANY_NAME_LOOKUP[symbol]

    return _clean_ticker(symbol)


def _company_aliases(ticker: str) -> set[str]:
    symbol = (ticker or "").upper()
    clean_symbol = _clean_ticker(symbol)
    company_name = get_company_name(symbol)

    aliases: set[str] = {company_name, clean_symbol, symbol}

    tokens = re.split(r"[^A-Za-z0-9]+", company_name.lower())
    for token in tokens:
        normalized = token.strip()
        if len(normalized) < 3:
            continue
        if normalized in _COMMON_NAME_WORDS:
            continue
        aliases.add(normalized)

    if clean_symbol == "META":
        aliases.add("facebook")

    return {alias for alias in aliases if alias and alias.strip()}


def _matches_ticker_content(text: str, ticker: str) -> bool:
    content = (text or "").lower()
    if not content:
        return False

    candidates = _company_aliases(ticker)
    for candidate in candidates:
        lowered = candidate.lower().strip()
        if not lowered:
            continue
        if " " in lowered:
            if lowered in content:
                return True
        else:
            if re.search(rf"\b{re.escape(lowered)}\b", content):
                return True

    return False


def _source_order_for_ticker(ticker: str) -> list[str]:
    if is_indian_stock(ticker):
        return ["rss", "gnews", "alpha_vantage"]
    return ["rss", "finnhub", "alpha_vantage", "gnews"]


def _get_cached(ticker: str) -> list | None:
    cache_key = (ticker or "").upper()
    with _news_cache_lock:
        cached = _news_cache.get(cache_key)
        if cached is None:
            return None

        headlines, timestamp = cached
        if (time.time() - timestamp) <= NEWS_CACHE_TTL:
            logger.info("[NEWS] %s: cache hit (TTL)", cache_key)
            return headlines

    return None


def _set_cached(ticker: str, headlines: list) -> None:
    cache_key = (ticker or "").upper()
    with _news_cache_lock:
        _news_cache[cache_key] = (headlines, time.time())


def _normalize_record(
    *,
    ticker: str,
    headline: str,
    summary: str,
    published: object,
    url: str,
    source: str,
) -> NewsEvent:
    return NewsEvent(
        headline=headline.strip(),
        summary=(summary or "").strip(),
        published=_normalize_published(published),
        url=(url or "").strip(),
        source=(source or "news").strip(),
        ticker_mentions=[ticker],
    )


class NewsConnector(BaseConnector):
    """Fetch ticker-related headlines from RSS and optional API providers."""

    def __init__(self, feeds: Optional[list[str]] = None) -> None:
        """Initialize connector with optional provider order overrides."""
        self.source_overrides: list[str] | None = feeds
        self.last_events: list[NewsEvent] = []

    def _rss_feeds_for_ticker(self, ticker: str) -> list[str]:
        return INDIAN_RSS_FEEDS if is_indian_stock(ticker) else US_RSS_FEEDS

    @staticmethod
    def _parse_rss_with_timeout(url: str) -> feedparser.FeedParserDict:
        def _worker() -> feedparser.FeedParserDict:
            return feedparser.parse(
                url,
                agent="crowd-signal/1.0",
                request_headers={
                    "User-Agent": "crowd-signal/1.0 (research tool)",
                    "Connection": "close",
                },
            )

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_worker)
            return future.result(timeout=_FEED_TIMEOUT_SECONDS)

    def _extract_rss_events(
        self,
        *,
        parsed: feedparser.FeedParserDict,
        ticker: str,
        url: str,
    ) -> list[NewsEvent]:
        source = str(parsed.feed.get("title") or url.split("/")[2])
        events: list[NewsEvent] = []

        for entry in parsed.entries:
            if len(events) >= _DEFAULT_LIMIT:
                break

            headline = str(entry.get("title", "")).strip()
            summary = str(entry.get("summary", entry.get("description", ""))).strip()
            if not headline and not summary:
                continue

            body = f"{headline} {summary}"
            if not _matches_ticker_content(body, ticker):
                continue

            events.append(
                _normalize_record(
                    ticker=ticker,
                    headline=headline,
                    summary=summary,
                    published=entry.get("published") or entry.get("updated") or "",
                    url=str(entry.get("link", "")),
                    source=source,
                )
            )

        return events

    async def fetch_rss(self, ticker: str) -> list[NewsEvent]:
        feeds = self._rss_feeds_for_ticker(ticker)
        logger.info("[NEWS] %s: trying RSS across %s feeds", ticker, len(feeds))

        collected: list[NewsEvent] = []
        for idx, feed_url in enumerate(feeds, start=1):
            logger.info("[NEWS] %s: RSS %s/%s %s", ticker, idx, len(feeds), feed_url)
            try:
                parsed = await asyncio.to_thread(self._parse_rss_with_timeout, feed_url)
            except FutureTimeoutError:
                logger.error("[NEWS] %s: RSS timeout for %s", ticker, feed_url)
                continue
            except Exception as exc:  # noqa: BLE001
                logger.error("[NEWS] %s: RSS failed for %s - %s", ticker, feed_url, str(exc))
                continue

            entry_count = len(parsed.entries)
            logger.info("[NEWS] %s: RSS entries=%s from %s", ticker, entry_count, feed_url)

            matched = self._extract_rss_events(parsed=parsed, ticker=ticker, url=feed_url)
            if matched:
                logger.info("[NEWS] %s: RSS matched %s headlines from %s", ticker, len(matched), feed_url)
                collected.extend(matched)
            else:
                logger.info("[NEWS] %s: RSS matched 0 headlines from %s", ticker, feed_url)

            if idx < len(feeds):
                await asyncio.sleep(_PER_FEED_DELAY_SECONDS)

            if len(collected) >= _DEFAULT_LIMIT:
                break

        deduped: list[NewsEvent] = []
        seen: set[tuple[str, str]] = set()
        for event in collected:
            key = (event.headline.lower(), event.url)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(event)

        return deduped[:_DEFAULT_LIMIT]

    async def fetch_finnhub(self, ticker: str) -> list[NewsEvent]:
        api_key = os.getenv("FINNHUB_API_KEY", "").strip()
        if not api_key:
            logger.warning("[NEWS] %s: Finnhub skipped - missing FINNHUB_API_KEY", ticker)
            return []

        clean_ticker = _clean_ticker(ticker)
        today = datetime.now(tz=timezone.utc).date()
        yesterday = today - timedelta(days=1)
        url = "https://finnhub.io/api/v1/company-news"
        params = {
            "symbol": clean_ticker,
            "from": yesterday.isoformat(),
            "to": today.isoformat(),
            "token": api_key,
        }

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list):
            raise RuntimeError(f"unexpected Finnhub response: {payload}")

        events: list[NewsEvent] = []
        for item in payload[:_DEFAULT_LIMIT]:
            headline = str(item.get("headline", "")).strip()
            if not headline:
                continue
            events.append(
                _normalize_record(
                    ticker=ticker,
                    headline=headline,
                    summary=str(item.get("summary", "")),
                    published=item.get("datetime"),
                    url=str(item.get("url", "")),
                    source=str(item.get("source", "finnhub")),
                )
            )

        return events

    async def fetch_alpha_vantage(self, ticker: str) -> list[NewsEvent]:
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
        if not api_key:
            logger.warning("[NEWS] %s: Alpha Vantage skipped - missing ALPHA_VANTAGE_API_KEY", ticker)
            return []

        clean_ticker = _clean_ticker(ticker)
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": clean_ticker,
            "apikey": api_key,
            "limit": _DEFAULT_LIMIT,
        }

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise RuntimeError(f"unexpected Alpha Vantage response: {payload}")

        for error_key in ("Error Message", "Information", "Note"):
            if payload.get(error_key):
                raise RuntimeError(str(payload[error_key]))

        feed = payload.get("feed", [])
        if not isinstance(feed, list):
            raise RuntimeError(f"unexpected Alpha Vantage feed payload: {feed}")

        events: list[NewsEvent] = []
        for item in feed[:_DEFAULT_LIMIT]:
            headline = str(item.get("title", "")).strip()
            if not headline:
                continue
            events.append(
                _normalize_record(
                    ticker=ticker,
                    headline=headline,
                    summary=str(item.get("summary", "")),
                    published=item.get("time_published"),
                    url=str(item.get("url", "")),
                    source=str(item.get("source", "alphavantage")),
                )
            )

        return events

    async def fetch_gnews(self, ticker: str) -> list[NewsEvent]:
        api_key = os.getenv("GNEWS_API_KEY", "").strip()
        if not api_key:
            logger.warning("[NEWS] %s: GNews skipped - missing GNEWS_API_KEY", ticker)
            return []

        company_name = get_company_name(ticker)
        query_symbol = _clean_ticker(ticker)

        url = "https://gnews.io/api/v4/search"
        params = {
            "q": f'"{company_name}" OR "{query_symbol}"',
            "token": api_key,
            "lang": "en",
            "max": _DEFAULT_LIMIT,
        }

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise RuntimeError(f"unexpected GNews response: {payload}")

        if payload.get("errors"):
            raise RuntimeError(str(payload["errors"]))

        articles = payload.get("articles", [])
        if not isinstance(articles, list):
            raise RuntimeError(f"unexpected GNews articles payload: {articles}")

        events: list[NewsEvent] = []
        for article in articles[:_DEFAULT_LIMIT]:
            headline = str(article.get("title", "")).strip()
            if not headline:
                continue

            source_value = article.get("source", {})
            if isinstance(source_value, dict):
                source_name = str(source_value.get("name", "gnews"))
            else:
                source_name = str(source_value or "gnews")

            events.append(
                _normalize_record(
                    ticker=ticker,
                    headline=headline,
                    summary=str(article.get("description", "")),
                    published=article.get("publishedAt"),
                    url=str(article.get("url", "")),
                    source=source_name,
                )
            )

        return events

    async def fetch(self, ticker: str) -> list[dict]:
        """Fetch normalized news records for *ticker* with explicit source diagnostics."""
        self.last_events = []

        cached = _get_cached(ticker)
        if cached is not None:
            return cached

        fetchers: dict[str, ProviderFetcher] = {
            "rss": self.fetch_rss,
            "finnhub": self.fetch_finnhub,
            "alpha_vantage": self.fetch_alpha_vantage,
            "gnews": self.fetch_gnews,
        }
        source_labels = {
            "rss": "RSS",
            "finnhub": "Finnhub",
            "alpha_vantage": "Alpha Vantage",
            "gnews": "GNews",
        }

        source_order = self.source_overrides or _source_order_for_ticker(ticker)

        for source_name in source_order:
            fetcher = fetchers.get(source_name)
            label = source_labels.get(source_name, source_name)
            if fetcher is None:
                logger.warning("[NEWS] %s: unknown source override %s - skipping", ticker, source_name)
                continue

            logger.info("[NEWS] %s: trying %s", ticker, label)
            try:
                results = await fetcher(ticker)
            except Exception as exc:  # noqa: BLE001
                logger.error("[NEWS] %s: %s failed - %s", ticker, label, str(exc))
                continue

            if results:
                self.last_events = results
                logger.info("[NEWS] %s: %s returned %s headlines", ticker, label, len(results))
                break

            logger.info("[NEWS] %s: %s returned 0 headlines", ticker, label)

        if not self.last_events:
            logger.warning("[NEWS] %s: all sources failed - 0 headlines", ticker)

        results = [
            {
                "type": "news",
                "ticker": ticker,
                "headline": event.headline,
                "summary": event.summary,
                "published": event.published.isoformat(),
                "url": event.url,
                "source": event.source,
                "ticker_mentions": event.ticker_mentions,
            }
            for event in self.last_events
        ]

        _set_cached(ticker, results)
        return results
