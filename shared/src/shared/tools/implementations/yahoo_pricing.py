"""Current price fetcher using Yahoo Finance.

Fetches live prices for Indian stocks via yfinance.
Tries .NS (NSE) then .BO (BSE) suffix for each ticker.
Batches requests where possible.
"""

from __future__ import annotations

import logging
from datetime import datetime

from shared.tools.pricing import GetCurrentPrice, PriceResult

logger = logging.getLogger(__name__)


class YahooPriceFetcher(GetCurrentPrice):
    """Fetch current prices from Yahoo Finance for Indian stocks."""

    def __init__(self) -> None:
        self._cache: dict[str, PriceResult] = {}

    async def get_prices(
        self,
        tickers: list[str],
        exchange: str = "BSE",
    ) -> list[PriceResult]:
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed")
            return [
                PriceResult(ticker=t, error="yfinance not installed")
                for t in tickers
            ]

        results: list[PriceResult] = []

        for ticker in tickers:
            # Check cache (prices valid for a few minutes in same session)
            if ticker in self._cache:
                results.append(self._cache[ticker])
                continue

            result = await self._fetch_single(ticker, yf)
            self._cache[ticker] = result
            results.append(result)

        logger.info(
            "Fetched prices for %d tickers, %d successful",
            len(tickers),
            sum(1 for r in results if r.current_price is not None),
        )

        return results

    async def _fetch_single(self, ticker: str, yf) -> PriceResult:
        """Fetch price for a single ticker."""
        tickers_to_try = [ticker]
        if not ticker.endswith((".NS", ".BO")):
            tickers_to_try = [f"{ticker}.NS", f"{ticker}.BO"]

        for t in tickers_to_try:
            try:
                stock = yf.Ticker(t)
                info = stock.info or {}

                price = info.get("currentPrice") or info.get("regularMarketPrice")
                if not price:
                    continue

                prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
                day_change = None
                day_change_pct = None
                if price and prev_close:
                    day_change = round(price - prev_close, 2)
                    day_change_pct = round(day_change / prev_close * 100, 2)

                result = PriceResult(
                    ticker=ticker,
                    current_price=price,
                    currency=info.get("currency", "INR"),
                    previous_close=prev_close,
                    day_change=day_change,
                    day_change_pct=day_change_pct,
                    volume=info.get("volume"),
                    market_cap=info.get("marketCap"),
                    fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
                    fifty_two_week_low=info.get("fiftyTwoWeekLow"),
                    retrieved_at=datetime.now(),
                    source=f"Yahoo Finance ({t})",
                )

                logger.info("Price for %s: ₹%.2f (via %s)", ticker, price, t)
                return result

            except Exception as e:
                logger.debug("Failed to fetch %s: %s", t, e)
                continue

        logger.warning("No price data for %s", ticker)
        return PriceResult(
            ticker=ticker,
            error=f"No price data found for {ticker}",
            retrieved_at=datetime.now(),
        )

    def clear_cache(self) -> None:
        self._cache.clear()
