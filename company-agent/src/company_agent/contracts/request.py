"""Typed request contract for the Company Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from shared.domain.enums import InvocationContext, ResearchDepth, SourceTier


@dataclass
class AuthorizedSources:
    permitted_tiers: list[SourceTier] = field(default_factory=lambda: list(SourceTier))
    max_secondary_sources: int = 10
    allow_opinion_sources: bool = False


@dataclass
class CompanyResearchRequest:
    request_id: str
    invocation_context: InvocationContext
    research_question: str
    issuer_candidate: str
    requested_as_of: date
    period_scope: str
    authorized_sources: AuthorizedSources
    caller_context: str
    research_depth: ResearchDepth
    market_cap_policy_version: str
    security_candidate: str | None = None
    exchange_hint: str | None = None
    fund_holding_date: date | None = None
    fund_identifier: str | None = None
    fund_share_class: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.request_id:
            errors.append("request_id is required")
        if not self.research_question.strip():
            errors.append("research_question must be a non-empty bounded question")
        if not self.issuer_candidate.strip():
            errors.append("issuer_candidate is required")
        if not self.period_scope.strip():
            errors.append("period_scope is required")
        if not self.caller_context.strip():
            errors.append("caller_context is required")
        if not self.market_cap_policy_version.strip():
            errors.append("market_cap_policy_version is required")
        if self.invocation_context == InvocationContext.FUND_UNDERLYING:
            if self.fund_holding_date is None:
                errors.append("fund_holding_date is required for fund_underlying invocation")
            if not self.fund_identifier:
                errors.append("fund_identifier is required for fund_underlying invocation")
        return errors
