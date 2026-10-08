"""Tool registry — holds the concrete tool implementations for a run.

The agent accesses tools only through this registry, making it easy
to swap between stub, test, and real implementations.
"""

from __future__ import annotations

from dataclasses import dataclass

from company_agent.tools.base import (
    ExtractEvidence,
    FindSourceConflicts,
    GetMarketCapClassification,
    GetValuationContext,
    ResolveIssuerSecurity,
    RetrieveSourceRecord,
    SearchPrimarySources,
    ValidateClaims,
)
from company_agent.tools.llm.base import LLMProvider


@dataclass
class ToolRegistry:
    """Container for all tool implementations needed by the agent."""

    resolve_issuer_security: ResolveIssuerSecurity
    search_primary_sources: SearchPrimarySources
    retrieve_source_record: RetrieveSourceRecord
    extract_evidence: ExtractEvidence
    find_source_conflicts: FindSourceConflicts
    get_market_cap_classification: GetMarketCapClassification
    get_valuation_context: GetValuationContext
    validate_claims: ValidateClaims
    llm: LLMProvider
