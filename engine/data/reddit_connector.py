"""Reddit connector — fetches recent top posts from finance subreddits via PRAW."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import praw
from dotenv import load_dotenv

from .base_connector import BaseConnector

load_dotenv()

_DEFAULT_SUBREDDITS: list[str] = ["wallstreetbets", "stocks"]
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

        self._reddit = praw.Reddit(
            client_id=os.environ.get("REDDIT_CLIENT_ID", ""),
            client_secret=os.environ.get("REDDIT_CLIENT_SECRET", ""),
            user_agent=os.environ.get(
                "REDDIT_USER_AGENT", "crowd-signal/0.1"
            ),
        )

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

    # ------------------------------------------------------------------
    # BaseConnector implementation
    # ------------------------------------------------------------------

    def fetch(self, ticker: str) -> list[dict]:
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

        for sub_name in self.subreddits:
            try:
                subreddit = self._reddit.subreddit(sub_name)
                for post in subreddit.hot(limit=_FETCH_LIMIT):
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
                            "selftext": post.selftext[:500],  # truncate for memory
                            "score": post.score,
                            "upvote_ratio": post.upvote_ratio,
                            "num_comments": post.num_comments,
                            "url": f"https://reddit.com{post.permalink}",
                            "created_utc": datetime.fromtimestamp(
                                post.created_utc, tz=timezone.utc
                            ).isoformat(),
                        }
                    )
            except Exception:
                # Auth errors or network failures must be non-fatal
                pass

        return results
