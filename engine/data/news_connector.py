"""News connector — polls Reuters and MarketWatch RSS feeds via feedparser."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import re

import feedparser

from .base_connector import BaseConnector

# RSS feed URLs for financial news
_RSS_FEEDS: list[str] = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
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
        self.feeds: list[str] = feeds or _RSS_FEEDS
        self.last_events: list[NewsEvent] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_feed(self, url: str, ticker: str) -> list[NewsEvent]:
        """Download and parse a single RSS *url*, filtering by *ticker*."""
        events: list[NewsEvent] = []
        parsed = feedparser.parse(url)
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

    # ------------------------------------------------------------------
    # BaseConnector implementation
    # ------------------------------------------------------------------

    def fetch(self, ticker: str) -> list[dict]:
        """Fetch news events for *ticker* from all configured RSS feeds.

        Args:
            ticker: Ticker symbol used to filter relevant articles.

        Returns:
            A list of dicts — one per :class:`NewsEvent` — with keys:
            ``type``, ``ticker``, ``headline``, ``summary``,
            ``published``, ``url``, ``source``, ``ticker_mentions``.
        """
        self.last_events = []
        for feed_url in self.feeds:
            try:
                self.last_events.extend(self._parse_feed(feed_url, ticker))
            except Exception:
                # Network or parse errors must not crash the simulation
                pass

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
