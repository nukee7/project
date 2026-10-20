"""Current price tool interface — shared across all agents.

Fetches live stock prices for one or more tickers.
Used by the Portfolio Agent to calculate current portfolio value.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PriceResult:
    """Price data for a single ticker."""

    ticker: str
    current_price: float | None = None
    currency: str = "INR"
    previous_close: float | None = None
    day_change: float | None = None
    day_change_pct: float | None = None
    volume: int | None = None
    market_cap: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    retrieved_at: datetime | None = None
    source: str = ""
    error: str | None = None


class GetCurrentPrice(ABC):
    """Fetch current stock prices for one or more tickers.

    Guardrail: Return retrieved_at timestamp. If a ticker
    can't be resolved, return PriceResult with error set.
    """

    @abstractmethod
    async def get_prices(
        self,
        tickers: list[str],
        exchange: str = "BSE",
    ) -> list[PriceResult]:
        ...
