"""Mutable workflow context that flows through the pipeline steps.

Each step reads from and writes to this context. It accumulates
identity resolution, sources, evidence, claims, and the final
work product sections as the pipeline progresses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from company_agent.contracts.request import CompanyResearchRequest
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
from company_agent.domain.claims import Claim
from company_agent.domain.enums import WorkProductStatus
from company_agent.domain.evidence import EvidenceRecord, SourceMetadata
from company_agent.domain.identity import IdentityResolution
from company_agent.domain.market_cap import MarketCapResult
from company_agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class ResearchPlan:
    """The plan created in Step 2 — what evidence is needed and why."""

    evidence_needs: list[dict[str, str]] = field(default_factory=list)
    # Each need: {"category": ..., "reason": ..., "unanswered_question": ...}
    source_categories: list[str] = field(default_factory=list)
    extraction_queries: dict[str, str] = field(default_factory=dict)
    # Maps source type → what to extract from it
    notes: str | None = None


@dataclass
class WorkflowContext:
    """Accumulated state as the pipeline progresses through steps.

    The pipeline is sequential — later steps depend on earlier verification.
    A tool failure or evidence conflict must remain visible in the output.
    """

    # Inputs
    request: CompanyResearchRequest
    tools: ToolRegistry

    # Step 1: Identity
    identity: IdentityResolution | None = None

    # Step 1A: Market cap
    market_cap: MarketCapResult | None = None

    # Step 2: Research plan
    research_plan: ResearchPlan | None = None

    # Step 3: Retrieved sources
    sources: list[SourceMetadata] = field(default_factory=list)

    # Step 4: Extracted evidence
    evidence_records: list[EvidenceRecord] = field(default_factory=list)

    # Step 5: Reconciled claims
    claims: list[Claim] = field(default_factory=list)

    # Step 5 (merged with old Step 6): Thesis + Company overview
    thesis: ThesisSection | None = None
    company_overview: CompanyOverviewSection | None = None

    # Accumulated state
    limitations: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    trace_log: list[str] = field(default_factory=list)

    # Pipeline control
    status: WorkProductStatus = WorkProductStatus.COMPLETE
    blocked_reason: str | None = None

    @property
    def is_blocked(self) -> bool:
        return self.status in (WorkProductStatus.BLOCKED, WorkProductStatus.NEEDS_REVIEW)

    def log(self, step: str, message: str) -> None:
        """Add an entry to the trace log."""
        entry = f"[{step}] {message}"
        self.trace_log.append(entry)
        logger.info(entry)

    def add_limitation(self, limitation: str) -> None:
        self.limitations.append(limitation)

    def add_open_question(self, question: str) -> None:
        self.open_questions.append(question)

    def block(self, reason: str) -> None:
        """Mark the workflow as blocked — stops further processing."""
        self.status = WorkProductStatus.BLOCKED
        self.blocked_reason = reason
        self.log("BLOCKED", reason)

    def mark_needs_review(self, reason: str) -> None:
        self.status = WorkProductStatus.NEEDS_REVIEW
        self.blocked_reason = reason
        self.log("NEEDS_REVIEW", reason)
