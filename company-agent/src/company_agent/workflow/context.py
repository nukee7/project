"""Mutable workflow context that flows through the pipeline steps."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from company_agent.contracts.request import CompanyResearchRequest
from company_agent.contracts.response import (
    CompanyOverviewSection, CompanyResearchResponse,
    EvidenceSummarySection, FinancialEvidenceSection,
    IdentitySection, LimitationsSection, MonitoringSection,
    ResearchScopeSection, ThesisSection, ValuationContextSection,
)
from shared.domain.claims import Claim
from shared.domain.enums import WorkProductStatus
from shared.domain.evidence import EvidenceRecord, SourceMetadata
from shared.domain.identity import IdentityResolution
from shared.domain.market_cap import MarketCapResult
from company_agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class ResearchPlan:
    evidence_needs: list[dict[str, str]] = field(default_factory=list)
    source_categories: list[str] = field(default_factory=list)
    extraction_queries: dict[str, str] = field(default_factory=dict)
    notes: str | None = None


@dataclass
class WorkflowContext:
    request: CompanyResearchRequest
    tools: ToolRegistry
    identity: IdentityResolution | None = None
    market_cap: MarketCapResult | None = None
    research_plan: ResearchPlan | None = None
    sources: list[SourceMetadata] = field(default_factory=list)
    evidence_records: list[EvidenceRecord] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    thesis: ThesisSection | None = None
    company_overview: CompanyOverviewSection | None = None
    limitations: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    trace_log: list[str] = field(default_factory=list)
    status: WorkProductStatus = WorkProductStatus.COMPLETE
    blocked_reason: str | None = None

    @property
    def is_blocked(self) -> bool:
        return self.status in (WorkProductStatus.BLOCKED, WorkProductStatus.NEEDS_REVIEW)

    def log(self, step: str, message: str) -> None:
        entry = f"[{step}] {message}"
        self.trace_log.append(entry)
        logger.info(entry)

    def add_limitation(self, limitation: str) -> None:
        self.limitations.append(limitation)

    def add_open_question(self, question: str) -> None:
        self.open_questions.append(question)

    def block(self, reason: str) -> None:
        self.status = WorkProductStatus.BLOCKED
        self.blocked_reason = reason
        self.log("BLOCKED", reason)

    def mark_needs_review(self, reason: str) -> None:
        self.status = WorkProductStatus.NEEDS_REVIEW
        self.blocked_reason = reason
        self.log("NEEDS_REVIEW", reason)
