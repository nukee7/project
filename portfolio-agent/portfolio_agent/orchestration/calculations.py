"""Deterministic portfolio calculations.

These are not LLM — they're simple math on portfolio data.
The spec requires that all numerical results come from deterministic
engines, not from LLM reasoning.

For MVP: basic allocation and exposure calculations.
"""

from __future__ import annotations

from portfolio_agent.models.portfolio import Portfolio, Position


def calculate_allocation(portfolio: Portfolio) -> dict:
    """Calculate position weights and allocation breakdown.

    Returns:
        {"total_invested": ..., "total_current": ..., "positions": [...],
         "by_sector": {...}, "by_type": {...}}
    """
    total_invested = portfolio.total_invested
    total_current = portfolio.total_current_value

    positions = []
    by_sector: dict[str, float] = {}
    by_type: dict[str, float] = {}

    for p in portfolio.positions:
        value = p.current_value or p.invested_value
        weight = (value / total_invested * 100) if total_invested > 0 else 0

        positions.append({
            "ticker": p.ticker,
            "name": p.name,
            "type": p.position_type.value,
            "quantity": p.quantity,
            "avg_buy_price": p.avg_buy_price,
            "current_price": p.current_price,
            "invested_value": round(p.invested_value, 2),
            "current_value": round(value, 2),
            "weight_pct": round(weight, 2),
            "sector": p.sector or "Unknown",
            "pnl": round(value - p.invested_value, 2),
            "pnl_pct": round((value - p.invested_value) / p.invested_value * 100, 2) if p.invested_value > 0 else 0,
        })

        # Sector allocation
        sector = p.sector or "Unknown"
        by_sector[sector] = by_sector.get(sector, 0) + value

        # Type allocation
        ptype = p.position_type.value
        by_type[ptype] = by_type.get(ptype, 0) + value

    # Convert sector/type to percentages
    total_val = sum(by_sector.values()) or 1
    sector_pct = {k: round(v / total_val * 100, 2) for k, v in sorted(by_sector.items(), key=lambda x: -x[1])}
    type_pct = {k: round(v / total_val * 100, 2) for k, v in by_type.items()}

    # Sort positions by weight
    positions.sort(key=lambda x: -x["weight_pct"])

    return {
        "total_invested": round(total_invested, 2),
        "total_current_value": round(total_current, 2) if total_current else None,
        "total_pnl": round(total_current - total_invested, 2) if total_current else None,
        "total_pnl_pct": round((total_current - total_invested) / total_invested * 100, 2) if total_current and total_invested > 0 else None,
        "position_count": len(positions),
        "positions": positions,
        "by_sector": sector_pct,
        "by_type": type_pct,
    }


def calculate_concentration(portfolio: Portfolio) -> dict:
    """Calculate concentration metrics.

    Returns top holdings, HHI (Herfindahl-Hirschman Index), and warnings.
    """
    total_invested = portfolio.total_invested or 1

    weights = []
    for p in portfolio.positions:
        value = p.current_value or p.invested_value
        weight = value / total_invested * 100
        weights.append({
            "ticker": p.ticker,
            "name": p.name,
            "weight_pct": round(weight, 2),
        })

    weights.sort(key=lambda x: -x["weight_pct"])

    # HHI — sum of squared weights (0-10000, higher = more concentrated)
    hhi = sum(w["weight_pct"] ** 2 for w in weights)

    # Top 5 concentration
    top5_weight = sum(w["weight_pct"] for w in weights[:5])

    # Warnings
    warnings: list[str] = []
    for w in weights:
        if w["weight_pct"] > 20:
            warnings.append(f"{w['ticker']} is {w['weight_pct']:.1f}% of portfolio — high concentration")
    if top5_weight > 70:
        warnings.append(f"Top 5 holdings are {top5_weight:.1f}% of portfolio — concentrated")
    if hhi > 2500:
        warnings.append(f"HHI is {hhi:.0f} — highly concentrated portfolio")

    return {
        "top_holdings": weights[:10],
        "top5_weight_pct": round(top5_weight, 2),
        "hhi": round(hhi, 0),
        "concentration_level": "high" if hhi > 2500 else "moderate" if hhi > 1500 else "diversified",
        "warnings": warnings,
    }
