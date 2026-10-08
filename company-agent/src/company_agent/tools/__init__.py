"""Tool interfaces and registry for the Company Agent.

Tools expose narrow, validated operations. The agent requests tools,
but tools validate all identifiers, dates, scopes, and authorization
before execution.
"""

from company_agent.tools.base import (
    ResolveIssuerSecurity,
    SearchPrimarySources,
    RetrieveSourceRecord,
    ExtractEvidence,
    FindSourceConflicts,
    GetMarketCapClassification,
    GetValuationContext,
    ValidateClaims,
)
from company_agent.tools.registry import ToolRegistry

__all__ = [
    "ResolveIssuerSecurity",
    "SearchPrimarySources",
    "RetrieveSourceRecord",
    "ExtractEvidence",
    "FindSourceConflicts",
    "GetMarketCapClassification",
    "GetValuationContext",
    "ValidateClaims",
    "ToolRegistry",
]
