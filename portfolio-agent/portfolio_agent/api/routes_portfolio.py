"""Portfolio routes — view portfolio, manage positions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from portfolio_agent.auth.dependencies import get_current_user
from portfolio_agent.api.state import app_state

router = APIRouter()


# --- Schemas ---


class AddPositionRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker", examples=["RELIANCE"])
    name: str = Field(..., description="Company name", examples=["Reliance Industries Ltd."])
    quantity: float = Field(..., gt=0, description="Number of shares", examples=[50])
    avg_buy_price: float = Field(..., gt=0, description="Average buy price (INR)", examples=[2450.0])
    position_type: str = Field(default="equity", description="equity or mutual_fund")
    exchange: str = Field(default="BSE", description="BSE or NSE")
    sector: str | None = Field(default=None, description="Sector", examples=["Oil & Gas"])
    isin: str | None = Field(default=None)
    account: str = Field(default="default")
    notes: str | None = Field(default=None)


class UpdatePositionRequest(BaseModel):
    quantity: float | None = Field(default=None, gt=0)
    avg_buy_price: float | None = Field(default=None, gt=0)
    current_price: float | None = Field(default=None, gt=0)
    sector: str | None = Field(default=None)
    notes: str | None = Field(default=None)


class PositionResponse(BaseModel):
    position_id: str
    ticker: str
    name: str
    position_type: str
    exchange: str
    quantity: float
    avg_buy_price: float
    current_price: float | None
    invested_value: float
    current_value: float | None
    sector: str | None
    account: str
    notes: str | None


class PortfolioResponse(BaseModel):
    portfolio_id: str
    user_id: str
    name: str
    base_currency: str
    position_count: int
    total_invested: float
    total_current_value: float | None
    as_of: str
    positions: list[PositionResponse]


# --- Routes ---


@router.get("", response_model=PortfolioResponse, summary="View your portfolio")
async def get_portfolio(user: dict = Depends(get_current_user)) -> PortfolioResponse:
    """Get the user's portfolio with all positions."""
    user_id = user["user_id"]
    portfolio = app_state.portfolio_store.get_or_create_portfolio(user_id)

    return PortfolioResponse(
        portfolio_id=portfolio.portfolio_id,
        user_id=portfolio.user_id,
        name=portfolio.name,
        base_currency=portfolio.base_currency,
        position_count=portfolio.position_count,
        total_invested=round(portfolio.total_invested, 2),
        total_current_value=round(portfolio.total_current_value, 2) if portfolio.total_current_value else None,
        as_of=str(portfolio.as_of),
        positions=[
            PositionResponse(
                position_id=p.position_id,
                ticker=p.ticker,
                name=p.name,
                position_type=p.position_type.value,
                exchange=p.exchange,
                quantity=p.quantity,
                avg_buy_price=p.avg_buy_price,
                current_price=p.current_price,
                invested_value=round(p.invested_value, 2),
                current_value=round(p.current_value, 2) if p.current_value else None,
                sector=p.sector,
                account=p.account,
                notes=p.notes,
            )
            for p in portfolio.positions
        ],
    )


@router.get("/positions", response_model=list[PositionResponse], summary="List all positions")
async def list_positions(user: dict = Depends(get_current_user)) -> list[PositionResponse]:
    """List all positions in the user's portfolio."""
    portfolio = app_state.portfolio_store.get_or_create_portfolio(user["user_id"])
    return [
        PositionResponse(
            position_id=p.position_id,
            ticker=p.ticker,
            name=p.name,
            position_type=p.position_type.value,
            exchange=p.exchange,
            quantity=p.quantity,
            avg_buy_price=p.avg_buy_price,
            current_price=p.current_price,
            invested_value=round(p.invested_value, 2),
            current_value=round(p.current_value, 2) if p.current_value else None,
            sector=p.sector,
            account=p.account,
            notes=p.notes,
        )
        for p in portfolio.positions
    ]


@router.post("/positions", response_model=PositionResponse, status_code=201, summary="Add a position")
async def add_position(
    body: AddPositionRequest,
    user: dict = Depends(get_current_user),
) -> PositionResponse:
    """Add a new position to the portfolio."""
    position = app_state.portfolio_store.add_position(
        user_id=user["user_id"],
        ticker=body.ticker,
        name=body.name,
        quantity=body.quantity,
        avg_buy_price=body.avg_buy_price,
        position_type=body.position_type,
        exchange=body.exchange,
        sector=body.sector,
        isin=body.isin,
        account=body.account,
        notes=body.notes,
    )
    return PositionResponse(
        position_id=position.position_id,
        ticker=position.ticker,
        name=position.name,
        position_type=position.position_type.value,
        exchange=position.exchange,
        quantity=position.quantity,
        avg_buy_price=position.avg_buy_price,
        current_price=position.current_price,
        invested_value=round(position.invested_value, 2),
        current_value=round(position.current_value, 2) if position.current_value else None,
        sector=position.sector,
        account=position.account,
        notes=position.notes,
    )


@router.put("/positions/{position_id}", response_model=PositionResponse, summary="Update a position")
async def update_position(
    position_id: str,
    body: UpdatePositionRequest,
    user: dict = Depends(get_current_user),
) -> PositionResponse:
    """Update an existing position."""
    position = app_state.portfolio_store.update_position(
        user_id=user["user_id"],
        position_id=position_id,
        quantity=body.quantity,
        avg_buy_price=body.avg_buy_price,
        current_price=body.current_price,
        sector=body.sector,
        notes=body.notes,
    )
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    return PositionResponse(
        position_id=position.position_id,
        ticker=position.ticker,
        name=position.name,
        position_type=position.position_type.value,
        exchange=position.exchange,
        quantity=position.quantity,
        avg_buy_price=position.avg_buy_price,
        current_price=position.current_price,
        invested_value=round(position.invested_value, 2),
        current_value=round(position.current_value, 2) if position.current_value else None,
        sector=position.sector,
        account=position.account,
        notes=position.notes,
    )


@router.delete("/positions/{position_id}", summary="Remove a position")
async def delete_position(
    position_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Remove a position from the portfolio."""
    removed = app_state.portfolio_store.remove_position(user["user_id"], position_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Position not found")
    return {"status": "removed", "position_id": position_id}


@router.post("/refresh-prices", summary="Refresh live prices for all positions")
async def refresh_prices(user: dict = Depends(get_current_user)) -> dict:
    """Fetch current market prices from Yahoo Finance and update all positions.

    Call this before querying to get accurate current values and P&L.
    """
    portfolio = app_state.portfolio_store.get_portfolio(user["user_id"])
    if not portfolio or not portfolio.positions:
        raise HTTPException(status_code=400, detail="No positions to refresh")

    if not app_state.price_fetcher:
        raise HTTPException(status_code=503, detail="Price fetcher not available")

    tickers = [p.ticker for p in portfolio.positions]
    results = await app_state.price_fetcher.get_prices(tickers)

    updated = 0
    errors = []
    for price_result in results:
        if price_result.current_price is not None:
            # Find matching position(s) and update
            for p in portfolio.positions:
                if p.ticker.upper() == price_result.ticker.upper():
                    p.current_price = price_result.current_price
                    updated += 1
        elif price_result.error:
            errors.append(f"{price_result.ticker}: {price_result.error}")

    return {
        "status": "refreshed",
        "positions_updated": updated,
        "total_positions": len(portfolio.positions),
        "total_invested": round(portfolio.total_invested, 2),
        "total_current_value": round(portfolio.total_current_value, 2) if portfolio.total_current_value else None,
        "errors": errors if errors else None,
    }
