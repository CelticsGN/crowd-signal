"""engine.data — data connector package for Crowd Signal."""

from .base_connector import BaseConnector
from .yfinance_connector import YFinanceConnector
from .news_connector import NewsConnector, NewsEvent
from .reddit_connector import RedditConnector

__all__ = [
    "BaseConnector",
    "YFinanceConnector",
    "NewsConnector",
    "NewsEvent",
    "RedditConnector",
]
