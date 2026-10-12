"""Domain models — re-exported from the shared package for backward compatibility.

All domain models now live in the shared package. This module
re-exports them so existing code can still import from
company_agent.domain if needed, but new code should import
from shared.domain directly.
"""

from shared.domain import (
    ClaimStatus, ClaimType, InvocationContext, MarketCapClassification,
    ResearchDepth, SourceTier, WorkProductStatus,
    ExchangeListing, IssuerIdentity, SecurityIdentity, IdentityResolution,
    EvidenceRecord, SourceMetadata,
    Claim, MarketCapResult,
)

__all__ = [
    "ClaimStatus", "ClaimType", "InvocationContext", "MarketCapClassification",
    "ResearchDepth", "SourceTier", "WorkProductStatus",
    "ExchangeListing", "IssuerIdentity", "SecurityIdentity", "IdentityResolution",
    "EvidenceRecord", "SourceMetadata",
    "Claim", "MarketCapResult",
]
