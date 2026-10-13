"""Tool registry — holds all tool implementations for a run.

Imports shared tools from the shared package and agent-specific
tools from this package.
"""

from __future__ import annotations

from dataclasses import dataclass

# Shared tools (used by all agents)
from shared.tools.identity import ResolveIssuerSecurity
from shared.tools.market_cap import GetMarketCapClassification
from shared.tools.claims import FindSourceConflicts, ValidateClaims

# Agent-specific tools
from company_agent.tools.base import (
    ExtractEvidence,
    GetValuationContext,
    RetrieveSourceRecord,
    SearchPrimarySources,
    SearchSecondarySources,
)
from company_agent.tools.llm.base import LLMProvider


@dataclass
class ToolRegistry:
    """Container for all tool implementations needed by the Company Agent."""

    # Shared tools
    resolve_issuer_security: ResolveIssuerSecurity
    get_market_cap_classification: GetMarketCapClassification
    find_source_conflicts: FindSourceConflicts
    validate_claims: ValidateClaims

    # Agent-specific tools
    search_primary_sources: SearchPrimarySources
    retrieve_source_record: RetrieveSourceRecord
    extract_evidence: ExtractEvidence
    search_secondary_sources: SearchSecondarySources
    get_valuation_context: GetValuationContext
    llm: LLMProvider
