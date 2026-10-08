"""Typed request contract for the Company Agent.

The spec requires the caller to provide a typed request. The agent must
reject or return needs_review for requests that lack enough identity
or time scope to produce reliable research.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from company_agent.domain.enums import InvocationContext, ResearchDepth, SourceTier


@dataclass
class AuthorizedSources:
    """Source tiers and retrieval permissions available to this invocation."""

    permitted_tiers: list[SourceTier] = field(default_factory=lambda: list(SourceTier))
    max_secondary_sources: int = 10
    allow_opinion_sources: bool = False


@dataclass
class CompanyResearchRequest:
    """The required input contract from the spec's request table.

    Every field marked required in the spec is non-optional here.
    The agent validates completeness before starting work.
    """

    # --- Required fields ---
    request_id: str
    invocation_context: InvocationContext
    research_question: str
    issuer_candidate: str                       # Company name or identifier from caller
    requested_as_of: date                       # Latest date the answer may cover
    period_scope: str                           # e.g. "FY2023-FY2024", "trailing 4 quarters"
    authorized_sources: AuthorizedSources
    caller_context: str                         # Why the work is requested
    research_depth: ResearchDepth
    market_cap_policy_version: str              # Versioned classification rules

    # --- Optional fields ---
    security_candidate: str | None = None       # Ticker, ISIN, CUSIP, etc. when known
    exchange_hint: str | None = None            # e.g. "NASDAQ" to disambiguate

    # --- Fund-underlying specific (required when invocation_context is fund_underlying) ---
    fund_holding_date: date | None = None       # Disclosed holding date
    fund_identifier: str | None = None          # Fund/share-class identifier
    fund_share_class: str | None = None

    def validate(self) -> list[str]:
        """Return a list of validation errors. Empty list means valid."""
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

        # Fund-underlying requires additional fields
        if self.invocation_context == InvocationContext.FUND_UNDERLYING:
            if self.fund_holding_date is None:
                errors.append(
                    "fund_holding_date is required for fund_underlying invocation"
                )
            if not self.fund_identifier:
                errors.append(
                    "fund_identifier is required for fund_underlying invocation"
                )

        return errors
