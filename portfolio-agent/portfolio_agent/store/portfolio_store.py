"""In-memory portfolio store. Replace with a database for production."""

from __future__ import annotations

import uuid
from datetime import datetime

from portfolio_agent.models.portfolio import Portfolio, Position


class PortfolioStore:
    """In-memory portfolio and position storage per user."""

    def __init__(self) -> None:
        self._portfolios: dict[str, Portfolio] = {}      # portfolio_id → Portfolio
        self._user_portfolios: dict[str, str] = {}       # user_id → portfolio_id (one per user for MVP)

    def get_or_create_portfolio(self, user_id: str) -> Portfolio:
        """Get the user's portfolio, or create one if it doesn't exist."""
        portfolio_id = self._user_portfolios.get(user_id)
        if portfolio_id and portfolio_id in self._portfolios:
            return self._portfolios[portfolio_id]

        # Create new portfolio
        portfolio_id = uuid.uuid4().hex[:12]
        portfolio = Portfolio(
            portfolio_id=portfolio_id,
            user_id=user_id,
        )
        self._portfolios[portfolio_id] = portfolio
        self._user_portfolios[user_id] = portfolio_id
        return portfolio

    def get_portfolio(self, user_id: str) -> Portfolio | None:
        """Get the user's portfolio. Returns None if no portfolio exists."""
        portfolio_id = self._user_portfolios.get(user_id)
        if portfolio_id:
            return self._portfolios.get(portfolio_id)
        return None

    def add_position(
        self,
        user_id: str,
        ticker: str,
        name: str,
        quantity: float,
        avg_buy_price: float,
        position_type: str = "equity",
        exchange: str = "BSE",
        sector: str | None = None,
        isin: str | None = None,
        account: str = "default",
        notes: str | None = None,
    ) -> Position:
        """Add a position to the user's portfolio."""
        from portfolio_agent.models.portfolio import PositionType

        portfolio = self.get_or_create_portfolio(user_id)

        position = Position(
            position_id=uuid.uuid4().hex[:12],
            ticker=ticker.upper().strip(),
            name=name.strip(),
            position_type=PositionType(position_type),
            exchange=exchange.upper().strip(),
            quantity=quantity,
            avg_buy_price=avg_buy_price,
            sector=sector,
            isin=isin,
            account=account,
            notes=notes,
        )
        portfolio.positions.append(position)
        portfolio.as_of = datetime.now()
        return position

    def remove_position(self, user_id: str, position_id: str) -> bool:
        """Remove a position from the user's portfolio. Returns True if found."""
        portfolio = self.get_portfolio(user_id)
        if not portfolio:
            return False
        before = len(portfolio.positions)
        portfolio.positions = [p for p in portfolio.positions if p.position_id != position_id]
        portfolio.as_of = datetime.now()
        return len(portfolio.positions) < before

    def update_position(
        self,
        user_id: str,
        position_id: str,
        quantity: float | None = None,
        avg_buy_price: float | None = None,
        current_price: float | None = None,
        sector: str | None = None,
        notes: str | None = None,
    ) -> Position | None:
        """Update fields on an existing position."""
        portfolio = self.get_portfolio(user_id)
        if not portfolio:
            return None
        position = portfolio.get_position(position_id)
        if not position:
            return None

        if quantity is not None:
            position.quantity = quantity
        if avg_buy_price is not None:
            position.avg_buy_price = avg_buy_price
        if current_price is not None:
            position.current_price = current_price
        if sector is not None:
            position.sector = sector
        if notes is not None:
            position.notes = notes

        portfolio.as_of = datetime.now()
        return position

    def clear_portfolio(self, user_id: str) -> bool:
        """Remove all positions from a user's portfolio."""
        portfolio = self.get_portfolio(user_id)
        if not portfolio:
            return False
        portfolio.positions.clear()
        portfolio.as_of = datetime.now()
        return True
