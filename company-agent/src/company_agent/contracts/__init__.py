"""Request and response contracts for the Company Agent."""

from company_agent.contracts.request import CompanyResearchRequest, AuthorizedSources
from company_agent.contracts.response import (
    CompanyResearchResponse,
    IdentitySection,
    ResearchScopeSection,
    EvidenceSummarySection,
    CompanyOverviewSection,
    FinancialEvidenceSection,
    ThesisSection,
    MonitoringSection,
    LimitationsSection,
    ValuationContextSection,
)

__all__ = [
    "CompanyResearchRequest",
    "AuthorizedSources",
    "CompanyResearchResponse",
    "IdentitySection",
    "ResearchScopeSection",
    "EvidenceSummarySection",
    "CompanyOverviewSection",
    "FinancialEvidenceSection",
    "ThesisSection",
    "MonitoringSection",
    "LimitationsSection",
    "ValuationContextSection",
]
