"""Stub tool implementations for development and testing.

These return plausible fake data so the agent workflow can run end-to-end
without real data providers. NOT for production use.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from company_agent.domain.claims import Claim
from company_agent.domain.enums import (
    ClaimStatus,
    MarketCapClassification,
    SourceTier,
)
from company_agent.domain.evidence import EvidenceRecord, SourceMetadata
from company_agent.domain.identity import (
    ExchangeListing,
    IdentityResolution,
    IssuerIdentity,
    SecurityIdentity,
)
from company_agent.domain.market_cap import MarketCapResult
from company_agent.tools.base import (
    ClaimValidationResult,
    ConflictResult,
    ExtractEvidence,
    FindSourceConflicts,
    GetMarketCapClassification,
    GetValuationContext,
    ResolveIssuerSecurity,
    RetrieveSourceRecord,
    SearchPrimarySources,
    SourceSearchResult,
    ValidateClaims,
)
from company_agent.tools.registry import ToolRegistry
from company_agent.testing.stub_llm import StubLLMProvider


def _uid() -> str:
    return uuid.uuid4().hex[:12]


class StubResolveIssuerSecurity(ResolveIssuerSecurity):
    """Returns a single high-confidence match for any input."""

    async def resolve(
        self,
        issuer_candidate: str,
        security_candidate: str | None = None,
        exchange_hint: str | None = None,
        as_of_date: date | None = None,
    ) -> IdentityResolution:
        ticker = security_candidate or issuer_candidate[:4].upper()
        exchange = exchange_hint or "NASDAQ"

        issuer = IssuerIdentity(
            name=issuer_candidate,
            identifiers={"stub_id": _uid()},
            country_of_incorporation="US",
        )
        security = SecurityIdentity(
            issuer=issuer,
            listings=[
                ExchangeListing(
                    exchange=exchange,
                    ticker=ticker,
                    currency="USD",
                )
            ],
            share_class="Common",
        )
        return IdentityResolution(
            resolved_issuer=issuer,
            resolved_security=security,
            candidates_considered=[issuer_candidate],
            resolution_source="stub_identity_service",
            confidence="high",
            as_of_date=as_of_date or date.today(),
        )


class StubSearchPrimarySources(SearchPrimarySources):
    """Returns a small set of fake source metadata."""

    async def search(
        self,
        issuer_name: str,
        issuer_identifiers: dict[str, str] | None = None,
        period_scope: str | None = None,
        source_types: list[str] | None = None,
        max_results: int = 20,
    ) -> SourceSearchResult:
        sources = [
            SourceMetadata(
                source_id=f"src_{_uid()}",
                publisher="SEC EDGAR",
                title=f"{issuer_name} — 10-K Annual Report",
                source_url=f"https://sec.gov/stub/{_uid()}",
                publication_date=date(2024, 3, 1),
                reporting_period=period_scope or "FY2024",
                retrieval_time=datetime.now(),
                source_tier=SourceTier.PRIMARY_FILING,
            ),
            SourceMetadata(
                source_id=f"src_{_uid()}",
                publisher=f"{issuer_name} Investor Relations",
                title=f"{issuer_name} — Q4 2024 Earnings Release",
                source_url=f"https://ir.example.com/stub/{_uid()}",
                publication_date=date(2024, 1, 28),
                reporting_period="Q4 2024",
                retrieval_time=datetime.now(),
                source_tier=SourceTier.PRIMARY_ISSUER,
            ),
        ]
        return SourceSearchResult(
            sources=sources[:max_results],
            total_available=len(sources),
            search_query=f"issuer={issuer_name} period={period_scope}",
        )


class StubRetrieveSourceRecord(RetrieveSourceRecord):
    """Returns the source metadata as-is (simulates successful retrieval)."""

    async def retrieve(
        self,
        source_id: str,
        source_url: str | None = None,
    ) -> SourceMetadata | None:
        return SourceMetadata(
            source_id=source_id,
            publisher="stub_publisher",
            title=f"Retrieved document {source_id}",
            source_url=source_url or f"https://stub.example.com/{source_id}",
            retrieval_time=datetime.now(),
            source_tier=SourceTier.PRIMARY_FILING,
        )


class StubExtractEvidence(ExtractEvidence):
    """Returns a single plausible evidence record per source."""

    async def extract(
        self,
        source: SourceMetadata,
        extraction_query: str,
        scope: str | None = None,
    ) -> list[EvidenceRecord]:
        return [
            EvidenceRecord(
                evidence_id=f"ev_{_uid()}",
                source=source,
                excerpt=f"[Stub excerpt for '{extraction_query}' from {source.title}]",
                locator=f"Section 7, page 42 of {source.source_id}",
                applicable_period=source.reporting_period,
                units_or_currency="USD",
                extraction_confidence="medium",
                tags=[extraction_query],
            )
        ]


class StubFindSourceConflicts(FindSourceConflicts):
    """Reports no conflicts (stub baseline)."""

    async def find_conflicts(
        self,
        evidence_records: list[EvidenceRecord],
        scope: str | None = None,
    ) -> ConflictResult:
        return ConflictResult(conflicts_found=False)


class StubGetMarketCapClassification(GetMarketCapClassification):
    """Returns a large-cap stub classification."""

    async def classify(
        self,
        issuer_name: str,
        security_identifier: str | None = None,
        as_of_date: date | None = None,
        policy_version: str | None = None,
    ) -> MarketCapResult:
        return MarketCapResult(
            classification=MarketCapClassification.LARGE_CAP,
            market_cap_value=150_000_000_000.0,
            currency="USD",
            as_of_date=as_of_date or date.today(),
            policy_version=policy_version or "v1.0",
            calculation_id=f"mkcap_{_uid()}",
            share_count_source="stub_share_data",
            price_source="stub_price_feed",
        )


class StubGetValuationContext(GetValuationContext):
    """Returns a minimal stub valuation context."""

    async def get_valuation(
        self,
        issuer_name: str,
        security_identifier: str | None = None,
        as_of_date: date | None = None,
        metrics: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "available": False,
            "reason": "Valuation context not configured in stub implementation",
        }


class StubValidateClaims(ValidateClaims):
    """Marks all claims as valid (stub baseline)."""

    async def validate(
        self,
        claims: list[Claim],
        evidence_records: list[EvidenceRecord],
    ) -> ClaimValidationResult:
        return ClaimValidationResult(
            valid_claims=[c.claim_id for c in claims],
            invalid_claims=[],
            issues=[],
        )


def create_stub_registry() -> ToolRegistry:
    """Create a ToolRegistry with all stub implementations."""
    return ToolRegistry(
        resolve_issuer_security=StubResolveIssuerSecurity(),
        search_primary_sources=StubSearchPrimarySources(),
        retrieve_source_record=StubRetrieveSourceRecord(),
        extract_evidence=StubExtractEvidence(),
        find_source_conflicts=StubFindSourceConflicts(),
        get_market_cap_classification=StubGetMarketCapClassification(),
        get_valuation_context=StubGetValuationContext(),
        validate_claims=StubValidateClaims(),
        llm=StubLLMProvider(),
    )
