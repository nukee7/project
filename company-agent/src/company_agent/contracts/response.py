"""Typed response contract for the Company Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from shared.domain.enums import InvocationContext, ResearchDepth, WorkProductStatus
from shared.domain.identity import IdentityResolution
from shared.domain.claims import Claim
from shared.domain.evidence import SourceMetadata
from shared.domain.market_cap import MarketCapResult


@dataclass
class IdentitySection:
    resolution: IdentityResolution
    notes: str | None = None


@dataclass
class ResearchScopeSection:
    research_question: str
    requested_as_of: str
    period_scope: str
    research_depth: ResearchDepth
    invocation_context: InvocationContext


@dataclass
class EvidenceSummarySection:
    primary_sources: list[SourceMetadata] = field(default_factory=list)
    secondary_sources: list[SourceMetadata] = field(default_factory=list)
    source_count: int = 0
    periods_covered: list[str] = field(default_factory=list)


@dataclass
class CompanyOverviewSection:
    business_description: str | None = None
    revenue_drivers: list[str] = field(default_factory=list)
    competitive_position: str | None = None
    governance_notes: str | None = None
    geographic_footprint: str | None = None
    supporting_claims: list[str] = field(default_factory=list)


@dataclass
class FinancialEvidenceSection:
    claims: list[Claim] = field(default_factory=list)
    periods_covered: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass
class ValuationContextSection:
    available: bool = False
    method: str | None = None
    inputs_description: str | None = None
    calculation_id: str | None = None
    as_of_date: str | None = None
    result_summary: str | None = None


@dataclass
class ThesisSection:
    hypothesis: str | None = None
    supporting_evidence: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    bull_case: str | None = None
    bear_case: str | None = None
    counter_thesis: str | None = None
    catalysts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    validation_signals: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)


@dataclass
class MonitoringSection:
    monitoring_signals: list[str] = field(default_factory=list)
    refresh_triggers: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)


@dataclass
class LimitationsSection:
    evidence_gaps: list[str] = field(default_factory=list)
    source_conflicts: list[str] = field(default_factory=list)
    stale_sources: list[str] = field(default_factory=list)
    scope_exclusions: list[str] = field(default_factory=list)


@dataclass
class CompanyResearchResponse:
    request_id: str
    agent: str = "company_agent"
    agent_version: str = "0.1.0"
    status: WorkProductStatus = WorkProductStatus.COMPLETE
    summary: str = ""
    identity: IdentitySection | None = None
    research_scope: ResearchScopeSection | None = None
    evidence_summary: EvidenceSummarySection | None = None
    company_overview: CompanyOverviewSection | None = None
    financial_evidence: FinancialEvidenceSection | None = None
    market_cap_classification: MarketCapResult | None = None
    valuation_context: ValuationContextSection | None = None
    thesis: ThesisSection | None = None
    monitoring: MonitoringSection | None = None
    limitations: LimitationsSection | None = None
    claims: list[Claim] = field(default_factory=list)
    calculation_refs: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    trace_refs: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    processing_time_seconds: float | None = None
