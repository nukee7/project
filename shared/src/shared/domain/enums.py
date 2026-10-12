"""Enumerations used across all agents."""

from enum import Enum


class InvocationContext(str, Enum):
    DIRECT_POSITION = "direct_position"
    FUND_UNDERLYING = "fund_underlying"
    STANDALONE_RESEARCH = "standalone_research"


class ResearchDepth(str, Enum):
    SCREEN = "screen"
    STANDARD = "standard"
    DEEP = "deep"


class SourceTier(str, Enum):
    PRIMARY_FILING = "primary_filing"
    PRIMARY_ISSUER = "primary_issuer"
    OFFICIAL_NOTICE = "official_notice"
    SECONDARY_LICENSED = "secondary_licensed"
    OPINION = "opinion"


class ClaimType(str, Enum):
    SOURCED_FACT = "sourced_fact"
    CALCULATED_RESULT = "calculated_result"
    INFERENCE = "inference"
    OPINION = "opinion"


class ClaimStatus(str, Enum):
    SUPPORTED = "supported"
    CONTESTED = "contested"
    STALE = "stale"
    SUPERSEDED = "superseded"
    UNVERIFIED = "unverified"
    NEEDS_REVIEW = "needs_review"


class MarketCapClassification(str, Enum):
    SMALL_CAP = "small_cap"
    MID_CAP = "mid_cap"
    LARGE_CAP = "large_cap"
    UNKNOWN = "unknown"


class WorkProductStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"
