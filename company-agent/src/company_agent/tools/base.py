"""Agent-specific tool interfaces for the Company Agent.

Shared tools (identity, market_cap, claims, conflicts) live in the
shared package. This file contains only Company Agent-specific tools:
- SearchPrimarySources (filing/document search)
- RetrieveSourceRecord (document fetching)
- ExtractEvidence (document parsing)
- GetValuationContext (valuation engine)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from shared.domain.evidence import EvidenceRecord, SourceMetadata


# --- Agent-specific result wrapper ---


@dataclass
class SourceSearchResult:
    """Result from searching for primary sources."""

    sources: list[SourceMetadata] = field(default_factory=list)
    total_available: int = 0
    search_query: str = ""
    notes: str | None = None


# --- Agent-specific tool interfaces ---


class SearchPrimarySources(ABC):
    """Locate filings and official materials.

    Guardrail: Enforce issuer and period filters; return source metadata.
    """

    @abstractmethod
    async def search(
        self,
        issuer_name: str,
        issuer_identifiers: dict[str, str] | None = None,
        period_scope: str | None = None,
        source_types: list[str] | None = None,
        max_results: int = 20,
    ) -> SourceSearchResult:
        ...


class RetrieveSourceRecord(ABC):
    """Fetch an approved source and locator.

    Guardrail: Record retrieval time, licensing limits, and immutable
    source reference.
    """

    @abstractmethod
    async def retrieve(
        self,
        source_id: str,
        source_url: str | None = None,
    ) -> SourceMetadata | None:
        ...


class ExtractEvidence(ABC):
    """Extract cited text or structured data from a source.

    Guardrail: Preserve excerpt, locator, period, units, and
    extraction confidence.
    """

    @abstractmethod
    async def extract(
        self,
        source: SourceMetadata,
        extraction_query: str,
        scope: str | None = None,
    ) -> list[EvidenceRecord]:
        ...


class GetValuationContext(ABC):
    """Retrieve defined, dated market-data calculations.

    Guardrail: Return methodology, inputs, currency, and calculation ID.
    """

    @abstractmethod
    async def get_valuation(
        self,
        issuer_name: str,
        security_identifier: str | None = None,
        as_of_date: object | None = None,
        metrics: list[str] | None = None,
    ) -> dict[str, object]:
        ...
