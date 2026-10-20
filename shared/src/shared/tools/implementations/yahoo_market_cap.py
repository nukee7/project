"""Market cap classification using Yahoo Finance.

Fetches market cap from yfinance, applies configurable thresholds
to classify as small_cap, mid_cap, or large_cap.

India-only: tries .NS (NSE) and .BO (BSE) suffixes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from shared.domain.enums import MarketCapClassification
from shared.domain.market_cap import MarketCapResult
from shared.tools.market_cap import GetMarketCapClassification

logger = logging.getLogger(__name__)

# Default INR thresholds (configurable via policy_version)
# These are approximate — real thresholds vary by index provider
DEFAULT_THRESHOLDS = {
    "v1.0": {
        "small_cap_max": 5_000_00_00_000,       # ₹5,000 Cr (₹50B)
        "mid_cap_max": 20_000_00_00_000,         # ₹20,000 Cr (₹200B)
        "currency": "INR",
    },
}


class YahooMarketCapClassifier(GetMarketCapClassification):
    """Classify company size using Yahoo Finance market cap data."""

    def __init__(self) -> None:
        self._cache: dict[str, dict] = {}

    async def classify(
        self,
        issuer_name: str,
        security_identifier: str | None = None,
        as_of_date: date | None = None,
        policy_version: str | None = None,
    ) -> MarketCapResult:
        if not security_identifier:
            return MarketCapResult(
                classification=MarketCapClassification.UNKNOWN,
                unavailable_reason="No ticker provided",
            )

        try:
            import yfinance as yf
        except ImportError:
            return MarketCapResult(
                classification=MarketCapClassification.UNKNOWN,
                unavailable_reason="yfinance not installed",
            )

        # Resolve ticker
        ticker = security_identifier
        info = await self._get_info(ticker)

        if not info or not info.get("marketCap"):
            return MarketCapResult(
                classification=MarketCapClassification.UNKNOWN,
                unavailable_reason=f"No market cap data for {ticker}",
            )

        market_cap = info["marketCap"]
        currency = info.get("currency", "INR")

        # Apply classification policy
        pv = policy_version or "v1.0"
        thresholds = DEFAULT_THRESHOLDS.get(pv, DEFAULT_THRESHOLDS["v1.0"])

        if market_cap < thresholds["small_cap_max"]:
            classification = MarketCapClassification.SMALL_CAP
        elif market_cap < thresholds["mid_cap_max"]:
            classification = MarketCapClassification.MID_CAP
        else:
            classification = MarketCapClassification.LARGE_CAP

        resolved = self._cache.get(f"{ticker}_resolved", ticker)

        logger.info(
            "Market cap for %s: %s (₹%.0f Cr), classified as %s",
            resolved, issuer_name, market_cap / 1e7, classification.value,
        )

        return MarketCapResult(
            classification=classification,
            market_cap_value=market_cap,
            currency=currency,
            as_of_date=as_of_date or date.today(),
            policy_version=pv,
            calculation_id=f"mkcap_{uuid.uuid4().hex[:12]}",
            share_count_source="Yahoo Finance",
            price_source=f"Yahoo Finance ({resolved})",
        )

    async def _get_info(self, ticker: str) -> dict | None:
        if ticker in self._cache:
            return self._cache[ticker]

        try:
            import yfinance as yf
        except ImportError:
            return None

        tickers_to_try = [ticker]
        if not ticker.endswith((".NS", ".BO")):
            tickers_to_try = [f"{ticker}.NS", f"{ticker}.BO"]

        for t in tickers_to_try:
            try:
                stock = yf.Ticker(t)
                info = stock.info or {}
                if info.get("marketCap"):
                    self._cache[ticker] = info
                    self._cache[f"{ticker}_resolved"] = t
                    return info
            except Exception:
                continue

        return None
