"""Tool interfaces and registry for the Company Agent."""

# Shared tools (re-exported for convenience)
from shared.tools.identity import ResolveIssuerSecurity
from shared.tools.market_cap import GetMarketCapClassification
from shared.tools.claims import FindSourceConflicts, ValidateClaims

# Agent-specific tools
from company_agent.tools.base import (
    SearchPrimarySources,
    RetrieveSourceRecord,
    ExtractEvidence,
    GetValuationContext,
    SourceSearchResult,
)
from company_agent.tools.registry import ToolRegistry

__all__ = [
    "ResolveIssuerSecurity",
    "GetMarketCapClassification",
    "FindSourceConflicts",
    "ValidateClaims",
    "SearchPrimarySources",
    "RetrieveSourceRecord",
    "ExtractEvidence",
    "GetValuationContext",
    "SourceSearchResult",
    "ToolRegistry",
]
