"""Market cap classification tool interface — shared across all agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from shared.domain.market_cap import MarketCapResult


class GetMarketCapClassification(ABC):
    """Retrieve the dated market-cap value and size classification.

    Guardrail: Return share-count and price input references, currency,
    as-of date, policy version, label, and calculation ID.
    """

    @abstractmethod
    async def classify(
        self,
        issuer_name: str,
        security_identifier: str | None = None,
        as_of_date: date | None = None,
        policy_version: str | None = None,
    ) -> MarketCapResult:
        ...
