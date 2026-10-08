"""Typed response contract for the Company Agent.

Maps to the "bounded work product" table from the spec:
identity, research_scope, evidence_summary, company_overview,
financial_and_operating_evidence, market_cap_classification,
valuation_context, thesis, monitoring, limitations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from company_agent.domain.enums import InvocationContext, ResearchDepth, WorkProductStatus
from company_agent.domain.identity import IdentityResolution
from company_agent.domain.claims import Claim
from company_agent.domain.evidence import SourceMetadata
from company_agent.domain.market_cap import MarketCapResult


# --- Work product sections ---


@dataclass
class IdentitySection:
    """Issuer/security resolution, listing/share class, confidence, and ambiguity."""

    resolution: IdentityResolution
    notes: str | None = None


@dataclass
class ResearchScopeSection:
    """What was asked and how the research was bounded."""

    research_question: str
    requested_as_of: str
    period_scope: str
    research_depth: ResearchDepth
    invocation_context: InvocationContext


@dataclass
class EvidenceSummarySection:
    """Material sources grouped by tier and reporting period."""

    primary_sources: list[SourceMetadata] = field(default_factory=list)
    secondary_sources: list[SourceMetadata] = field(default_factory=list)
    source_count: int = 0
    periods_covered: list[str] = field(default_factory=list)


@dataclass
class CompanyOverviewSection:
    """Cited business, operating, competitive, and governance information."""

    business_description: str | None = None
    revenue_drivers: list[str] = field(default_factory=list)
    competitive_position: str | None = None
    governance_notes: str | None = None
    geographic_footprint: str | None = None
    supporting_claims: list[str] = field(default_factory=list)  # Claim IDs


@dataclass
class FinancialEvidenceSection:
    """Period-specific sourced facts. No free-form arithmetic."""

    claims: list[Claim] = field(default_factory=list)
    periods_covered: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass
class ValuationContextSection:
    """Optional engine-backed output with method, inputs, and date."""

    available: bool = False
    method: str | None = None
    inputs_description: str | None = None
    calculation_id: str | None = None
    as_of_date: str | None = None
    result_summary: str | None = None


@dataclass
class ThesisSection:
    """The structured research thesis — testable, not a prediction."""

    hypothesis: str | None = None
    supporting_evidence: list[str] = field(default_factory=list)   # Claim IDs
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
    """Signals, refresh triggers, and invalidation conditions."""

    monitoring_signals: list[str] = field(default_factory=list)
    refresh_triggers: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)


@dataclass
class LimitationsSection:
    """Evidence gaps, conflicts, stale sources, and scope exclusions."""

    evidence_gaps: list[str] = field(default_factory=list)
    source_conflicts: list[str] = field(default_factory=list)
    stale_sources: list[str] = field(default_factory=list)
    scope_exclusions: list[str] = field(default_factory=list)


# --- Top-level work product ---


@dataclass
class CompanyResearchResponse:
    """The complete Company Agent work product.

    Uses the common envelope fields from the shared agent contract
    plus Company Agent-specific sections.
    """

    # Common envelope
    request_id: str
    agent: str = "company_agent"
    agent_version: str = "0.1.0"
    status: WorkProductStatus = WorkProductStatus.COMPLETE
    summary: str = ""

    # Company Agent sections
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

    # Common envelope (continued)
    claims: list[Claim] = field(default_factory=list)
    calculation_refs: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    trace_refs: list[str] = field(default_factory=list)

    # Metadata
    created_at: datetime | None = None
    processing_time_seconds: float | None = None
