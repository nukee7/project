"""Market capitalization classification model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from shared.domain.enums import MarketCapClassification


@dataclass
class MarketCapResult:
    classification: MarketCapClassification
    market_cap_value: float | None = None
    currency: str | None = None
    as_of_date: date | None = None
    policy_version: str | None = None
    calculation_id: str | None = None
    share_count_source: str | None = None
    price_source: str | None = None
    unavailable_reason: str | None = None
