"""Stub tool implementations for development and testing. NOT for production."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from shared.domain.claims import Claim
from shared.domain.enums import ClaimStatus, MarketCapClassification, SourceTier
from shared.domain.evidence import EvidenceRecord, SourceMetadata
from shared.domain.identity import (
    ExchangeListing, IdentityResolution, IssuerIdentity, SecurityIdentity,
)
from shared.domain.market_cap import MarketCapResult
from shared.tools.identity import ResolveIssuerSecurity
from shared.tools.market_cap import GetMarketCapClassification
from shared.tools.claims import FindSourceConflicts, ValidateClaims
from shared.tools.results import ClaimValidationResult, ConflictResult
from company_agent.tools.base import (
    ExtractEvidence, GetValuationContext, RetrieveSourceRecord,
    SearchPrimarySources, SearchSecondarySources, SourceSearchResult,
)
from company_agent.tools.registry import ToolRegistry
from test.company_agent.stub_llm import StubLLMProvider


def _uid() -> str:
    return uuid.uuid4().hex[:12]


class StubResolveIssuerSecurity(ResolveIssuerSecurity):
    async def resolve(self, issuer_candidate, security_candidate=None, exchange_hint=None, as_of_date=None):
        ticker = security_candidate or issuer_candidate[:4].upper()
        exchange = exchange_hint or "NASDAQ"
        issuer = IssuerIdentity(name=issuer_candidate, identifiers={"stub_id": _uid()}, country_of_incorporation="US")
        security = SecurityIdentity(issuer=issuer, listings=[ExchangeListing(exchange=exchange, ticker=ticker, currency="USD")], share_class="Common")
        return IdentityResolution(resolved_issuer=issuer, resolved_security=security, candidates_considered=[issuer_candidate], resolution_source="stub_identity_service", confidence="high", as_of_date=as_of_date or date.today())


class StubSearchPrimarySources(SearchPrimarySources):
    async def search(self, issuer_name, issuer_identifiers=None, period_scope=None, source_types=None, max_results=20):
        sources = [
            SourceMetadata(source_id=f"src_{_uid()}", publisher="BSE India", title=f"{issuer_name} — Annual Financial Result", source_url=f"https://bseindia.com/stub/{_uid()}", publication_date=date(2024, 3, 1), reporting_period=period_scope or "FY2024", retrieval_time=datetime.now(), source_tier=SourceTier.PRIMARY_FILING),
            SourceMetadata(source_id=f"src_{_uid()}", publisher="BSE India", title=f"{issuer_name} — Q4 Financial Result", source_url=f"https://bseindia.com/stub/{_uid()}", publication_date=date(2024, 1, 28), reporting_period="Q4 2024", retrieval_time=datetime.now(), source_tier=SourceTier.PRIMARY_ISSUER),
        ]
        return SourceSearchResult(sources=sources[:max_results], total_available=len(sources), search_query=f"issuer={issuer_name} period={period_scope}")


class StubRetrieveSourceRecord(RetrieveSourceRecord):
    async def retrieve(self, source_id, source_url=None):
        return SourceMetadata(source_id=source_id, publisher="stub_publisher", title=f"Retrieved document {source_id}", source_url=source_url or f"https://stub.example.com/{source_id}", retrieval_time=datetime.now(), source_tier=SourceTier.PRIMARY_FILING)


class StubExtractEvidence(ExtractEvidence):
    async def extract(self, source, extraction_query, scope=None):
        return [EvidenceRecord(evidence_id=f"ev_{_uid()}", source=source, excerpt=f"[Stub excerpt for '{extraction_query}' from {source.title}]", locator=f"Section 7, page 42 of {source.source_id}", applicable_period=source.reporting_period, units_or_currency="USD", extraction_confidence="medium", tags=[extraction_query])]


class StubFindSourceConflicts(FindSourceConflicts):
    async def find_conflicts(self, evidence_records, scope=None):
        return ConflictResult(conflicts_found=False)


class StubGetMarketCapClassification(GetMarketCapClassification):
    async def classify(self, issuer_name, security_identifier=None, as_of_date=None, policy_version=None):
        return MarketCapResult(classification=MarketCapClassification.LARGE_CAP, market_cap_value=150_000_000_000.0, currency="USD", as_of_date=as_of_date or date.today(), policy_version=policy_version or "v1.0", calculation_id=f"mkcap_{_uid()}", share_count_source="stub_share_data", price_source="stub_price_feed")


class StubValidateClaims(ValidateClaims):
    async def validate(self, claims, evidence_records):
        return ClaimValidationResult(valid_claims=[c.claim_id for c in claims], invalid_claims=[], issues=[])


class StubSearchSecondarySources(SearchSecondarySources, GetValuationContext):
    async def search(self, issuer_name, security_identifier=None, research_question=None, period_scope=None, max_results=10, search_queries=None):
        source = SourceMetadata(source_id=f"news_{_uid()}", publisher="Stub News", title=f"[Stub] News about {issuer_name}", retrieval_time=datetime.now(), source_tier=SourceTier.SECONDARY_LICENSED)
        return [EvidenceRecord(evidence_id=f"ev_{_uid()}", source=source, excerpt=f"[Stub] Analysts are generally positive about {issuer_name}.", locator="Stub Secondary Sources", extraction_confidence="low", tags=["news", "secondary", "stub"])]

    async def get_valuation(self, issuer_name, security_identifier=None, as_of_date=None, metrics=None):
        return {"available": False, "reason": "Stub — not configured"}


def create_stub_registry() -> ToolRegistry:
    secondary = StubSearchSecondarySources()
    return ToolRegistry(
        resolve_issuer_security=StubResolveIssuerSecurity(),
        search_primary_sources=StubSearchPrimarySources(),
        retrieve_source_record=StubRetrieveSourceRecord(),
        extract_evidence=StubExtractEvidence(),
        find_source_conflicts=StubFindSourceConflicts(),
        get_market_cap_classification=StubGetMarketCapClassification(),
        validate_claims=StubValidateClaims(),
        search_secondary_sources=secondary,
        llm=StubLLMProvider(),
    )
