"""Identity resolution tool interface — shared across all agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from shared.domain.identity import IdentityResolution


class ResolveIssuerSecurity(ABC):
    """Resolve issuer, security, listing, and share class.

    Guardrail: Return candidates and ambiguity; never silently select
    a close match.
    """

    @abstractmethod
    async def resolve(
        self,
        issuer_candidate: str,
        security_candidate: str | None = None,
        exchange_hint: str | None = None,
        as_of_date: date | None = None,
    ) -> IdentityResolution:
        ...
