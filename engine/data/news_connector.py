"""News connector — polls Reuters and MarketWatch RSS feeds via feedparser."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Optional
import re

import feedparser

from .base_connector import BaseConnector
from .market_utils import is_indian_stock

logger = logging.getLogger(__name__)

# RSS feed URLs for financial news
US_RSS_FEEDS: list[str] = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
]

INDIAN_RSS_FEEDS: list[str] = [
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.moneycontrol.com/rss/MCtopnews.xml",
    "https://www.business-standard.com/rss/markets-106.rss",
]


@dataclass
class NewsEvent:
    """A single parsed news item from an RSS feed.

    Attributes:
        headline:        Article title as-is from the feed.
        summary:         Short article summary / description.
        published:       Publication datetime (UTC-aware).
        url:             Canonical link to the full article.
        ticker_mentions: Ticker symbols detected in the headline or summary.
        source:          Feed hostname for provenance tracking.
    """

    headline: str
    summary: str
    published: datetime
    url: str
    source: str
    ticker_mentions: list[str] = field(default_factory=list)


def _extract_tickers(text: str, target: Optional[str] = None) -> list[str]:
    """Extract uppercase 1-5 letter ticker-like tokens from *text*.

    If *target* is provided it is always included in the result when
    found (case-insensitive substring match).  Generic tokens like
    common English words are filtered out via a simple blocklist.
    """
    _BLOCKLIST = {"A", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HE", "I",
                  "IF", "IN", "IS", "IT", "ME", "MY", "NO", "OF", "ON", "OR",
                  "SO", "TO", "US", "WE", "AND", "FOR", "NOT", "THE", "ARE",
                  "BUT", "CAN", "GET", "HAS", "HAD", "HIM", "HIS", "HOW",
                  "ITS", "LET", "MAY", "NEW", "NOW", "OLD", "OUR", "OUT",
                  "OWN", "RAN", "SAY", "SHE", "TRY", "TWO", "USE", "WAY",
                  "WHO", "WHY", "YES", "YET", "YOU"}

    tokens = re.findall(r"\b[A-Z]{2,5}\b", text)
    found = [t for t in tokens if t not in _BLOCKLIST]

    if target and target.upper() in text.upper():
        tgt = target.upper()
        if tgt not in found:
            found.insert(0, tgt)

    return list(dict.fromkeys(found))  # deduplicate, preserve order


class NewsConnector(BaseConnector):
    """Polls Reuters and MarketWatch RSS feeds for news matching a ticker.

    Parsed entries are returned as both a list of :class:`NewsEvent`
    objects (accessible via :py:attr:`last_events`) and as plain dicts
    from :py:meth:`fetch`.
    """

    def __init__(self, feeds: Optional[list[str]] = None) -> None:
        """Initialise the connector.

        Args:
            feeds: Override the default RSS feed URLs if provided.
        """
        self.feeds: list[str] = feeds or US_RSS_FEEDS
        self.last_events: list[NewsEvent] = []

    def get_feeds(self, ticker: str) -> list[str]:
        if is_indian_stock(ticker):
            return INDIAN_RSS_FEEDS
        return self.feeds

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_feed(self, parsed: feedparser.FeedParserDict, url: str, ticker: str) -> list[NewsEvent]:
        """Download and parse a single RSS *url*, filtering by *ticker*."""
        events: list[NewsEvent] = []
        source = url.split("/")[2]  # hostname

        for entry in parsed.entries:
            headline: str = entry.get("title", "")
            summary: str = entry.get("summary", entry.get("description", ""))
            link: str = entry.get("link", "")

            # Best-effort datetime parsing
            published_struct = entry.get("published_parsed")
            if published_struct:
                published = datetime(*published_struct[:6], tzinfo=timezone.utc)
            else:
                published = datetime.now(tz=timezone.utc)

            mentions = _extract_tickers(headline + " " + summary, target=ticker)

            # Only keep entries that mention the ticker (or include any
            # market-relevant term when no ticker context is available)
            if ticker.upper() in (headline + summary).upper() or not ticker:
                events.append(
                    NewsEvent(
                        headline=headline,
                        summary=summary,
                        published=published,
                        url=link,
                        source=source,
                        ticker_mentions=mentions,
                    )
                )
        return events

    def _parse_with_timeout(self, url: str) -> feedparser.FeedParserDict:
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
            try:
                return future.result(timeout=8)
            except FutureTimeoutError as exc:
                raise TimeoutError(f"[NEWS] {url} timed out after 8s") from exc

    # ------------------------------------------------------------------
    # BaseConnector implementation
    # ------------------------------------------------------------------

    async def fetch(self, ticker: str) -> list[dict]:
        """Fetch news events for *ticker* from all configured RSS feeds.

        Args:
            ticker: Ticker symbol used to filter relevant articles.

        Returns:
            A list of dicts — one per :class:`NewsEvent` — with keys:
            ``type``, ``ticker``, ``headline``, ``summary``,
            ``published``, ``url``, ``source``, ``ticker_mentions``.
        """
        self.last_events = []
        logger.info("[NEWS] Fetching feeds for %s", ticker)
        for feed_url in self.get_feeds(ticker):
            try:
                logger.info("[NEWS] %s: trying feed %s", ticker, feed_url)
                parsed = await asyncio.to_thread(self._parse_with_timeout, feed_url)
                entries_count = len(getattr(parsed, "entries", []) or [])
                logger.info("[NEWS] %s: feed returned %s entries", ticker, entries_count)
                self.last_events.extend(self._parse_feed(parsed, feed_url, ticker))
            except TimeoutError as exc:
                logger.error(str(exc))
            except Exception as exc:  # noqa: BLE001
                logger.error("[NEWS] %s: feed %s FAILED - %s", ticker, feed_url, str(exc))
            await asyncio.sleep(0.5)

        logger.info("[NEWS] %s: total headlines after all feeds: %s", ticker, len(self.last_events))

        return [
            {
                "type": "news",
                "ticker": ticker,
                "headline": ev.headline,
                "summary": ev.summary,
                "published": ev.published.isoformat(),
                "url": ev.url,
                "source": ev.source,
                "ticker_mentions": ev.ticker_mentions,
            }
            for ev in self.last_events
        ]
