"""Pydantic models for the API layer.

These are adapter models that translate between HTTP JSON and the
domain dataclasses. The domain layer stays pure — Pydantic lives
only at the HTTP boundary.

Two sets of models:
- Request schemas: JSON → to_domain() → CompanyResearchRequest
- Response schemas: CompanyResearchResponse → from_domain() → JSON
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from company_agent.contracts.request import (
    AuthorizedSources,
    CompanyResearchRequest,
)
from company_agent.contracts.response import (
    CompanyOverviewSection,
    CompanyResearchResponse,
    EvidenceSummarySection,
    FinancialEvidenceSection,
    IdentitySection,
    LimitationsSection,
    MonitoringSection,
    ResearchScopeSection,
    ThesisSection,
    ValuationContextSection,
)
from shared.domain.claims import Claim
from shared.domain.enums import (
    ClaimStatus,
    ClaimType,
    InvocationContext,
    MarketCapClassification,
    ResearchDepth,
    SourceTier,
    WorkProductStatus,
)
from shared.domain.evidence import SourceMetadata
from shared.domain.identity import IdentityResolution
from shared.domain.market_cap import MarketCapResult


# ============================================================
# Request schemas
# ============================================================


class AuthorizedSourcesSchema(BaseModel):
    """Source tiers and retrieval permissions."""

    permitted_tiers: list[SourceTier] = Field(
        default_factory=lambda: list(SourceTier),
        description="Which source tiers this invocation may use",
    )
    max_secondary_sources: int = Field(
        default=10,
        description="Cap on secondary sources",
    )
    allow_opinion_sources: bool = Field(
        default=False,
        description="Whether analyst/opinion material is permitted",
    )

    def to_domain(self) -> AuthorizedSources:
        return AuthorizedSources(
            permitted_tiers=self.permitted_tiers,
            max_secondary_sources=self.max_secondary_sources,
            allow_opinion_sources=self.allow_opinion_sources,
        )


class ResearchRequestBody(BaseModel):
    """JSON request body for POST /research.

    Maps to CompanyResearchRequest. Pydantic handles type coercion
    (string dates → date objects, string enums → enum values) and
    structural validation. Business rules are validated by the domain.
    """

    model_config = {"json_schema_extra": {
        "examples": [{
            "request_id": "req-001",
            "invocation_context": "direct_position",
            "research_question": "What are the key revenue drivers and competitive risks?",
            "issuer_candidate": "Alphabet Inc.",
            "security_candidate": "GOOGL",
            "exchange_hint": "NASDAQ",
            "requested_as_of": "2024-12-31",
            "period_scope": "FY2023-FY2024",
            "caller_context": "Direct equity holding, reviewing annual thesis.",
            "research_depth": "standard",
            "market_cap_policy_version": "v1.0",
            "authorized_sources": {
                "permitted_tiers": ["primary_filing", "primary_issuer", "secondary_licensed"],
                "max_secondary_sources": 10,
                "allow_opinion_sources": False,
            },
        }]
    }}

    # Required fields
    request_id: str = Field(
        ..., description="Correlates the request, output, and audit trace"
    )
    invocation_context: InvocationContext = Field(
        ..., description="Why the agent was called: direct_position, fund_underlying, or standalone_research"
    )
    research_question: str = Field(
        ..., description="Bounded question to investigate"
    )
    issuer_candidate: str = Field(
        ..., description="Company name or identifier supplied by the caller"
    )
    requested_as_of: date = Field(
        ..., description="Latest date the answer is allowed to describe (ISO format)"
    )
    period_scope: str = Field(
        ..., description="Financial reporting periods to focus on, e.g. FY2023-FY2024"
    )
    authorized_sources: AuthorizedSourcesSchema = Field(
        default_factory=AuthorizedSourcesSchema,
        description="Source tiers and retrieval permissions",
    )
    caller_context: str = Field(
        ..., description="Why the work is requested"
    )
    research_depth: ResearchDepth = Field(
        ..., description="screen, standard, or deep"
    )
    market_cap_policy_version: str = Field(
        ..., description="Versioned rules defining small/mid/large cap"
    )

    # Optional fields
    security_candidate: str | None = Field(
        default=None, description="Ticker, ISIN, CUSIP, etc. when known"
    )
    exchange_hint: str | None = Field(
        default=None, description="Exchange name to disambiguate, e.g. NASDAQ"
    )

    # Fund-underlying specific
    fund_holding_date: date | None = Field(
        default=None, description="Disclosed holding date (required for fund_underlying)"
    )
    fund_identifier: str | None = Field(
        default=None, description="Fund/share-class identifier (required for fund_underlying)"
    )
    fund_share_class: str | None = Field(
        default=None, description="Fund share class"
    )

    def to_domain(self) -> CompanyResearchRequest:
        """Convert this Pydantic model to the domain dataclass."""
        return CompanyResearchRequest(
            request_id=self.request_id,
            invocation_context=self.invocation_context,
            research_question=self.research_question,
            issuer_candidate=self.issuer_candidate,
            requested_as_of=self.requested_as_of,
            period_scope=self.period_scope,
            authorized_sources=self.authorized_sources.to_domain(),
            caller_context=self.caller_context,
            research_depth=self.research_depth,
            market_cap_policy_version=self.market_cap_policy_version,
            security_candidate=self.security_candidate,
            exchange_hint=self.exchange_hint,
            fund_holding_date=self.fund_holding_date,
            fund_identifier=self.fund_identifier,
            fund_share_class=self.fund_share_class,
        )


# ============================================================
# Response schemas
# ============================================================


class ExchangeListingSchema(BaseModel):
    exchange: str
    ticker: str
    currency: str
    instrument_type: str = "common"


class IssuerIdentitySchema(BaseModel):
    name: str
    identifiers: dict[str, str] = Field(default_factory=dict)
    country_of_incorporation: str | None = None
    prior_names: list[str] = Field(default_factory=list)
    notes: str | None = None


class SecurityIdentitySchema(BaseModel):
    issuer: IssuerIdentitySchema
    listings: list[ExchangeListingSchema] = Field(default_factory=list)
    share_class: str | None = None
    isin: str | None = None
    cusip: str | None = None
    sedol: str | None = None


class IdentityResolutionSchema(BaseModel):
    resolved_issuer: IssuerIdentitySchema | None = None
    resolved_security: SecurityIdentitySchema | None = None
    candidates_considered: list[str] = Field(default_factory=list)
    resolution_source: str | None = None
    confidence: str = "unresolved"
    unresolved_ambiguity: str | None = None
    as_of_date: date | None = None

    @classmethod
    def from_domain(cls, obj: IdentityResolution) -> IdentityResolutionSchema:
        resolved_issuer = None
        if obj.resolved_issuer:
            i = obj.resolved_issuer
            resolved_issuer = IssuerIdentitySchema(
                name=i.name,
                identifiers=dict(i.identifiers),
                country_of_incorporation=i.country_of_incorporation,
                prior_names=list(i.prior_names),
                notes=i.notes,
            )

        resolved_security = None
        if obj.resolved_security:
            s = obj.resolved_security
            listings = [
                ExchangeListingSchema(
                    exchange=el.exchange,
                    ticker=el.ticker,
                    currency=el.currency,
                    instrument_type=el.instrument_type,
                )
                for el in s.listings
            ]
            resolved_security = SecurityIdentitySchema(
                issuer=IssuerIdentitySchema(
                    name=s.issuer.name,
                    identifiers=dict(s.issuer.identifiers),
                    country_of_incorporation=s.issuer.country_of_incorporation,
                    prior_names=list(s.issuer.prior_names),
                    notes=s.issuer.notes,
                ),
                listings=listings,
                share_class=s.share_class,
                isin=s.isin,
                cusip=s.cusip,
                sedol=s.sedol,
            )

        return cls(
            resolved_issuer=resolved_issuer,
            resolved_security=resolved_security,
            candidates_considered=list(obj.candidates_considered),
            resolution_source=obj.resolution_source,
            confidence=obj.confidence,
            unresolved_ambiguity=obj.unresolved_ambiguity,
            as_of_date=obj.as_of_date,
        )


class IdentitySectionSchema(BaseModel):
    resolution: IdentityResolutionSchema
    notes: str | None = None

    @classmethod
    def from_domain(cls, obj: IdentitySection) -> IdentitySectionSchema:
        return cls(
            resolution=IdentityResolutionSchema.from_domain(obj.resolution),
            notes=obj.notes,
        )


class SourceMetadataSchema(BaseModel):
    source_id: str
    publisher: str
    title: str
    source_url: str | None = None
    publication_date: date | None = None
    reporting_period: str | None = None
    retrieval_time: datetime | None = None
    source_tier: SourceTier = SourceTier.SECONDARY_LICENSED
    licensing_notes: str | None = None

    @classmethod
    def from_domain(cls, obj: SourceMetadata) -> SourceMetadataSchema:
        return cls(
            source_id=obj.source_id,
            publisher=obj.publisher,
            title=obj.title,
            source_url=obj.source_url,
            publication_date=obj.publication_date,
            reporting_period=obj.reporting_period,
            retrieval_time=obj.retrieval_time,
            source_tier=obj.source_tier,
            licensing_notes=obj.licensing_notes,
        )


class ClaimSchema(BaseModel):
    claim_id: str
    claim_type: ClaimType
    statement: str
    scope: str
    time_period: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    calculation_id: str | None = None
    status: ClaimStatus = ClaimStatus.UNVERIFIED
    conflict_explanation: str | None = None
    attribution: str | None = None

    @classmethod
    def from_domain(cls, obj: Claim) -> ClaimSchema:
        return cls(
            claim_id=obj.claim_id,
            claim_type=obj.claim_type,
            statement=obj.statement,
            scope=obj.scope,
            time_period=obj.time_period,
            evidence_ids=list(obj.evidence_ids),
            calculation_id=obj.calculation_id,
            status=obj.status,
            conflict_explanation=obj.conflict_explanation,
            attribution=obj.attribution,
        )


class MarketCapResultSchema(BaseModel):
    classification: MarketCapClassification
    market_cap_value: float | None = None
    currency: str | None = None
    as_of_date: date | None = None
    policy_version: str | None = None
    calculation_id: str | None = None
    share_count_source: str | None = None
    price_source: str | None = None
    unavailable_reason: str | None = None

    @classmethod
    def from_domain(cls, obj: MarketCapResult) -> MarketCapResultSchema:
        return cls(
            classification=obj.classification,
            market_cap_value=obj.market_cap_value,
            currency=obj.currency,
            as_of_date=obj.as_of_date,
            policy_version=obj.policy_version,
            calculation_id=obj.calculation_id,
            share_count_source=obj.share_count_source,
            price_source=obj.price_source,
            unavailable_reason=obj.unavailable_reason,
        )


class ResearchScopeSectionSchema(BaseModel):
    research_question: str
    requested_as_of: str
    period_scope: str
    research_depth: ResearchDepth
    invocation_context: InvocationContext

    @classmethod
    def from_domain(cls, obj: ResearchScopeSection) -> ResearchScopeSectionSchema:
        return cls(
            research_question=obj.research_question,
            requested_as_of=obj.requested_as_of,
            period_scope=obj.period_scope,
            research_depth=obj.research_depth,
            invocation_context=obj.invocation_context,
        )


class EvidenceSummarySectionSchema(BaseModel):
    primary_sources: list[SourceMetadataSchema] = Field(default_factory=list)
    secondary_sources: list[SourceMetadataSchema] = Field(default_factory=list)
    source_count: int = 0
    periods_covered: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, obj: EvidenceSummarySection) -> EvidenceSummarySectionSchema:
        return cls(
            primary_sources=[SourceMetadataSchema.from_domain(s) for s in obj.primary_sources],
            secondary_sources=[SourceMetadataSchema.from_domain(s) for s in obj.secondary_sources],
            source_count=obj.source_count,
            periods_covered=list(obj.periods_covered),
        )


class CompanyOverviewSectionSchema(BaseModel):
    business_description: str | None = None
    revenue_drivers: list[str] = Field(default_factory=list)
    competitive_position: str | None = None
    governance_notes: str | None = None
    geographic_footprint: str | None = None
    supporting_claims: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, obj: CompanyOverviewSection) -> CompanyOverviewSectionSchema:
        return cls(
            business_description=obj.business_description,
            revenue_drivers=list(obj.revenue_drivers),
            competitive_position=obj.competitive_position,
            governance_notes=obj.governance_notes,
            geographic_footprint=obj.geographic_footprint,
            supporting_claims=list(obj.supporting_claims),
        )


class FinancialEvidenceSectionSchema(BaseModel):
    claims: list[ClaimSchema] = Field(default_factory=list)
    periods_covered: list[str] = Field(default_factory=list)
    notes: str | None = None

    @classmethod
    def from_domain(cls, obj: FinancialEvidenceSection) -> FinancialEvidenceSectionSchema:
        return cls(
            claims=[ClaimSchema.from_domain(c) for c in obj.claims],
            periods_covered=list(obj.periods_covered),
            notes=obj.notes,
        )


class ValuationContextSectionSchema(BaseModel):
    available: bool = False
    method: str | None = None
    inputs_description: str | None = None
    calculation_id: str | None = None
    as_of_date: str | None = None
    result_summary: str | None = None

    @classmethod
    def from_domain(cls, obj: ValuationContextSection) -> ValuationContextSectionSchema:
        return cls(
            available=obj.available,
            method=obj.method,
            inputs_description=obj.inputs_description,
            calculation_id=obj.calculation_id,
            as_of_date=obj.as_of_date,
            result_summary=obj.result_summary,
        )


class ThesisSectionSchema(BaseModel):
    hypothesis: str | None = None
    supporting_evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    bull_case: str | None = None
    bear_case: str | None = None
    counter_thesis: str | None = None
    catalysts: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    validation_signals: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, obj: ThesisSection) -> ThesisSectionSchema:
        return cls(
            hypothesis=obj.hypothesis,
            supporting_evidence=list(obj.supporting_evidence),
            assumptions=list(obj.assumptions),
            bull_case=obj.bull_case,
            bear_case=obj.bear_case,
            counter_thesis=obj.counter_thesis,
            catalysts=list(obj.catalysts),
            risks=list(obj.risks),
            validation_signals=list(obj.validation_signals),
            invalidation_conditions=list(obj.invalidation_conditions),
        )


class MonitoringSectionSchema(BaseModel):
    monitoring_signals: list[str] = Field(default_factory=list)
    refresh_triggers: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, obj: MonitoringSection) -> MonitoringSectionSchema:
        return cls(
            monitoring_signals=list(obj.monitoring_signals),
            refresh_triggers=list(obj.refresh_triggers),
            invalidation_conditions=list(obj.invalidation_conditions),
        )


class LimitationsSectionSchema(BaseModel):
    evidence_gaps: list[str] = Field(default_factory=list)
    source_conflicts: list[str] = Field(default_factory=list)
    stale_sources: list[str] = Field(default_factory=list)
    scope_exclusions: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, obj: LimitationsSection) -> LimitationsSectionSchema:
        return cls(
            evidence_gaps=list(obj.evidence_gaps),
            source_conflicts=list(obj.source_conflicts),
            stale_sources=list(obj.stale_sources),
            scope_exclusions=list(obj.scope_exclusions),
        )


# --- Top-level response ---


class ResearchResponseBody(BaseModel):
    """JSON response body for POST /research.

    Maps from CompanyResearchResponse. Sections that didn't execute
    (because the pipeline blocked early) come back as null.
    """

    # Common envelope
    request_id: str
    agent: str = "company_agent"
    agent_version: str = "0.1.0"
    status: WorkProductStatus = WorkProductStatus.COMPLETE
    summary: str = ""

    # Company Agent sections
    identity: IdentitySectionSchema | None = None
    research_scope: ResearchScopeSectionSchema | None = None
    evidence_summary: EvidenceSummarySectionSchema | None = None
    company_overview: CompanyOverviewSectionSchema | None = None
    financial_evidence: FinancialEvidenceSectionSchema | None = None
    market_cap_classification: MarketCapResultSchema | None = None
    valuation_context: ValuationContextSectionSchema | None = None
    thesis: ThesisSectionSchema | None = None
    monitoring: MonitoringSectionSchema | None = None
    limitations: LimitationsSectionSchema | None = None

    # Common envelope (continued)
    claims: list[ClaimSchema] = Field(default_factory=list)
    calculation_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    trace_refs: list[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime | None = None
    processing_time_seconds: float | None = None

    @classmethod
    def from_domain(cls, resp: CompanyResearchResponse) -> ResearchResponseBody:
        """Convert a domain CompanyResearchResponse to this Pydantic model."""
        return cls(
            request_id=resp.request_id,
            agent=resp.agent,
            agent_version=resp.agent_version,
            status=resp.status,
            summary=resp.summary,
            identity=(
                IdentitySectionSchema.from_domain(resp.identity)
                if resp.identity else None
            ),
            research_scope=(
                ResearchScopeSectionSchema.from_domain(resp.research_scope)
                if resp.research_scope else None
            ),
            evidence_summary=(
                EvidenceSummarySectionSchema.from_domain(resp.evidence_summary)
                if resp.evidence_summary else None
            ),
            company_overview=(
                CompanyOverviewSectionSchema.from_domain(resp.company_overview)
                if resp.company_overview else None
            ),
            financial_evidence=(
                FinancialEvidenceSectionSchema.from_domain(resp.financial_evidence)
                if resp.financial_evidence else None
            ),
            market_cap_classification=(
                MarketCapResultSchema.from_domain(resp.market_cap_classification)
                if resp.market_cap_classification else None
            ),
            valuation_context=(
                ValuationContextSectionSchema.from_domain(resp.valuation_context)
                if resp.valuation_context else None
            ),
            thesis=(
                ThesisSectionSchema.from_domain(resp.thesis)
                if resp.thesis else None
            ),
            monitoring=(
                MonitoringSectionSchema.from_domain(resp.monitoring)
                if resp.monitoring else None
            ),
            limitations=(
                LimitationsSectionSchema.from_domain(resp.limitations)
                if resp.limitations else None
            ),
            claims=[ClaimSchema.from_domain(c) for c in resp.claims],
            calculation_refs=list(resp.calculation_refs),
            evidence_refs=list(resp.evidence_refs),
            open_questions=list(resp.open_questions),
            trace_refs=list(resp.trace_refs),
            created_at=resp.created_at,
            processing_time_seconds=resp.processing_time_seconds,
        )
