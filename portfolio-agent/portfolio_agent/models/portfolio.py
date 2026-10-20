"""Portfolio and Position models.

A portfolio is a collection of positions (holdings) owned by a user.
Each position is a specific security held in a specific account.

Positions can be:
- Direct equity (stocks listed on BSE/NSE)
- Mutual fund units

The portfolio carries an as-of timestamp — it's a snapshot,
not a live claim about what the user currently owns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class PositionType(str, Enum):
    """Type of holding."""

    EQUITY = "equity"
    MUTUAL_FUND = "mutual_fund"


@dataclass
class Position:
    """A single holding in the portfolio.

    Represents a specific security or fund held by the user.
    """

    position_id: str
    ticker: str                          # e.g. "RELIANCE", "INFY", "HDFC"
    name: str                            # e.g. "Reliance Industries Ltd."
    position_type: PositionType = PositionType.EQUITY
    exchange: str = "BSE"                # BSE or NSE
    quantity: float = 0.0                # Number of shares/units
    avg_buy_price: float = 0.0           # Average purchase price (INR)
    current_price: float | None = None   # Latest price (filled by market data)
    sector: str | None = None            # e.g. "IT", "Banking", "Oil & Gas"
    isin: str | None = None              # ISIN for precise identification
    account: str = "default"             # Account name
    added_at: datetime = field(default_factory=datetime.now)
    notes: str | None = None

    @property
    def invested_value(self) -> float:
        """Total amount invested."""
        return self.quantity * self.avg_buy_price

    @property
    def current_value(self) -> float | None:
        """Current market value, if price is available."""
        if self.current_price is not None:
            return self.quantity * self.current_price
        return None


@dataclass
class Portfolio:
    """A user's complete portfolio — a versioned set of positions.

    Distinguishes observed data (positions) from user-declared context
    (objectives, constraints) per the spec.
    """

    portfolio_id: str
    user_id: str
    name: str = "My Portfolio"
    base_currency: str = "INR"
    positions: list[Position] = field(default_factory=list)
    as_of: datetime = field(default_factory=datetime.now)

    # User-declared context (not observed data)
    investment_horizon: str | None = None     # e.g. "long_term", "3-5 years"
    risk_tolerance: str | None = None         # e.g. "moderate", "aggressive"
    objectives: str | None = None             # Free-form goals

    @property
    def total_invested(self) -> float:
        return sum(p.invested_value for p in self.positions)

    @property
    def total_current_value(self) -> float | None:
        values = [p.current_value for p in self.positions if p.current_value is not None]
        return sum(values) if values else None

    @property
    def position_count(self) -> int:
        return len(self.positions)

    def get_position(self, position_id: str) -> Position | None:
        for p in self.positions:
            if p.position_id == position_id:
                return p
        return None

    def get_positions_by_ticker(self, ticker: str) -> list[Position]:
        return [p for p in self.positions if p.ticker.upper() == ticker.upper()]
