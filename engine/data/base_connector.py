"""Base connector interface for all Crowd Signal data sources."""

from abc import ABC, abstractmethod


class BaseConnector(ABC):
    """Abstract base class that every data connector must implement.

    All connectors follow a uniform interface: given a ticker symbol,
    return a list of normalised dict records suitable for downstream
    consumption by the simulation engine.
    """

    @abstractmethod
    def fetch(self, ticker: str) -> list[dict]:
        """Retrieve data for the given ticker symbol.

        Args:
            ticker: The stock ticker to query (e.g. ``"NVDA"``).

        Returns:
            A list of dicts, each representing one data record.
        """
        ...
