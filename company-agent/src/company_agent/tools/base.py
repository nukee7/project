"""Abstract base classes for all Company Agent tools.

Each tool maps to a row in the spec's tool contract table. Tools validate
inputs and return structured results — the agent cannot bypass validation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

from company_agent.domain.claims import Claim
from company_agent.domain.evidence import EvidenceRecord, SourceMetadata
from company_agent.domain.identity import IdentityResolution
from company_agent.domain.market_cap import MarketCapResult


# --- Tool result wrappers ---


@dataclass
class SourceSearchResult:
    """Result from searching for primary sources."""

    sources: list[SourceMetadata] = field(default_factory=list)
    total_available: int = 0
    search_query: str = ""
    notes: str | None = None


@dataclass
class ConflictResult:
    """Result from conflict detection."""

    conflicts_found: bool = False
    conflicts: list[dict[str, str]] = field(default_factory=list)
    # Each conflict: {"claim_scope": ..., "source_a": ..., "source_b": ..., "description": ...}


@dataclass
class ClaimValidationResult:
    """Result from claim validation."""

    valid_claims: list[str] = field(default_factory=list)          # Claim IDs
    invalid_claims: list[str] = field(default_factory=list)        # Claim IDs
    issues: list[dict[str, str]] = field(default_factory=list)
    # Each issue: {"claim_id": ..., "issue": ..., "severity": ...}


# --- Abstract tool interfaces ---


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


class FindSourceConflicts(ABC):
    """Detect contradictory data for the same claim scope.

    Guardrail: Return conflicts rather than resolve them implicitly.
    """

    @abstractmethod
    async def find_conflicts(
        self,
        evidence_records: list[EvidenceRecord],
        scope: str | None = None,
    ) -> ConflictResult:
        ...


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


class GetValuationContext(ABC):
    """Retrieve defined, dated market-data calculations.

    Guardrail: Return methodology, inputs, currency, and calculation ID.
    """

    @abstractmethod
    async def get_valuation(
        self,
        issuer_name: str,
        security_identifier: str | None = None,
        as_of_date: date | None = None,
        metrics: list[str] | None = None,
    ) -> dict[str, object]:
        ...


class ValidateClaims(ABC):
    """Check claim evidence/scope/freshness completeness.

    Guardrail: Cannot upgrade an unsupported claim to supported.
    """

    @abstractmethod
    async def validate(
        self,
        claims: list[Claim],
        evidence_records: list[EvidenceRecord],
    ) -> ClaimValidationResult:
        ...
