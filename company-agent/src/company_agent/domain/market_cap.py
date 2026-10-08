"""Market capitalization classification model.

The agent does not calculate market cap itself — it receives
the result from a deterministic market-data service.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from company_agent.domain.enums import MarketCapClassification


@dataclass
class MarketCapResult:
    """Engine-backed market-cap classification result."""

    classification: MarketCapClassification
    market_cap_value: float | None = None       # In the specified currency
    currency: str | None = None                 # e.g. "USD"
    as_of_date: date | None = None
    policy_version: str | None = None           # Which classification policy was used
    calculation_id: str | None = None           # For audit trail
    share_count_source: str | None = None       # Where share count came from
    price_source: str | None = None             # Where price came from
    unavailable_reason: str | None = None       # If classification is UNKNOWN
