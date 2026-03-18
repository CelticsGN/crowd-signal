"""Reddit connector — fetches recent top posts from finance subreddits via PRAW."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import asyncpraw
from dotenv import load_dotenv

from .base_connector import BaseConnector
from .market_utils import is_indian_stock

load_dotenv()

logger = logging.getLogger(__name__)

INDIAN_SUBREDDITS: list[str] = [
    "IndiaInvestments",
    "IndianStreetBets",
    "NSEIndia",
    "DalalStreetTalks",
]

US_SUBREDDITS: list[str] = [
    "wallstreetbets",
    "stocks",
    "investing",
]

_DEFAULT_SUBREDDITS: list[str] = US_SUBREDDITS
_FETCH_LIMIT: int = 50  # posts per subreddit
_LOOKBACK_HOURS: float = 2.0


class RedditConnector(BaseConnector):
    """Fetches the most-recent top posts from r/wallstreetbets and r/stocks.

    Authentication credentials are read from the environment (or a
    ``.env`` file):

    * ``REDDIT_CLIENT_ID``
    * ``REDDIT_CLIENT_SECRET``
    * ``REDDIT_USER_AGENT``

    Only posts published within the last :py:attr:`lookback_hours` hours
    are returned so the simulation always works with fresh crowd signal.
    """

    def __init__(
        self,
        subreddits: list[str] | None = None,
        lookback_hours: float = _LOOKBACK_HOURS,
    ) -> None:
        """Initialise the connector.

        Args:
            subreddits:     List of subreddit names to query.
            lookback_hours: Only posts newer than this many hours are kept.
        """
        self.subreddits: list[str] = subreddits or _DEFAULT_SUBREDDITS
        self.lookback_hours: float = lookback_hours
        self._client_id = os.environ.get("REDDIT_CLIENT_ID", "").strip()
        self._client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
        self._user_agent = os.environ.get("REDDIT_USER_AGENT", "crowd-signal/1.0").strip()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_recent(self, created_utc: float) -> bool:
        """Return ``True`` if *created_utc* is within the lookback window."""
        age_hours = (
            datetime.now(tz=timezone.utc).timestamp() - created_utc
        ) / 3600
        return age_hours <= self.lookback_hours

    def _post_mentions(self, text: str, ticker: str) -> bool:
        """Return ``True`` when *text* references *ticker* (case-insensitive)."""
        return ticker.upper() in text.upper()

    def get_subreddits(self, ticker: str) -> list[str]:
        if is_indian_stock(ticker):
            return INDIAN_SUBREDDITS
        return US_SUBREDDITS

    # ------------------------------------------------------------------
    # BaseConnector implementation
    # ------------------------------------------------------------------

    async def fetch(self, ticker: str) -> list[dict]:
        """Fetch recent Reddit posts that mention *ticker*.

        Searches the hot queue of each configured subreddit and returns
        posts from the last :py:attr:`lookback_hours` hours that
        reference the ticker in their title or selftext.

        Args:
            ticker: Ticker symbol to filter posts by.

        Returns:
            A list of dicts with keys: ``type``, ``ticker``,
            ``subreddit``, ``title``, ``selftext``, ``score``,
            ``upvote_ratio``, ``num_comments``, ``url``, ``created_utc``.
        """
        results: list[dict] = []
        logger.info("[REDDIT] Fetching posts for %s", ticker)

        if not self._client_id or not self._client_secret:
            logger.warning("[REDDIT] credentials not configured - skipping")
            return results

        target_subreddits = self.get_subreddits(ticker)
        logger.info("[REDDIT] %s: subreddits=%s", ticker, target_subreddits)

        try:
            async with asyncpraw.Reddit(
                client_id=self._client_id,
                client_secret=self._client_secret,
                user_agent=self._user_agent,
            ) as reddit:
                for sub_name in target_subreddits:
                    try:
                        subreddit = await reddit.subreddit(sub_name)
                        async for post in subreddit.hot(limit=_FETCH_LIMIT):
                            if not self._is_recent(post.created_utc):
                                continue
                            combined = f"{post.title} {post.selftext}"
                            if not self._post_mentions(combined, ticker):
                                continue
                            results.append(
                                {
                                    "type": "reddit_post",
                                    "ticker": ticker,
                                    "subreddit": sub_name,
                                    "title": post.title,
                                    "selftext": post.selftext[:500],
                                    "score": post.score,
                                    "upvote_ratio": post.upvote_ratio,
                                    "num_comments": post.num_comments,
                                    "url": f"https://reddit.com{post.permalink}",
                                    "created_utc": datetime.fromtimestamp(
                                        post.created_utc, tz=timezone.utc
                                    ).isoformat(),
                                }
                            )
                    except Exception as exc:  # noqa: BLE001
                        text = str(exc).lower()
                        if "rate" in text and "limit" in text:
                            logger.error("[REDDIT] rate limited - %s", str(exc))
                        else:
                            logger.error("[REDDIT] %s: FAILED - %s", sub_name, str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.error("[REDDIT] credentials missing or invalid - %s", str(exc))
            return []

        logger.info("[REDDIT] %s: posts found: %s", ticker, len(results))

        return results
